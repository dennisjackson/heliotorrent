use axum::extract::State;
use axum::{
    Router,
    body::Body,
    extract::Path,
    http::{HeaderMap, Response, StatusCode, header},
    response::IntoResponse,
    routing::get,
};
use clap::Parser;
use lru::LruCache;
use reqwest::Client;
use serde::Deserialize;
use std::{collections::HashMap, net::SocketAddr, path::PathBuf, sync::Arc};
use std::{
    net::{IpAddr, Ipv6Addr},
    num::NonZeroUsize,
};
use tokio::fs;
use tokio::sync::Mutex;
use tower_http::services::ServeDir;
use tracing::{debug, error, info, instrument, warn};

use axum_server::tls_rustls::RustlsConfig;
use rustls_pemfile::{certs, private_key};
use std::io::BufReader;
use tokio_rustls::rustls::{self};

#[derive(Default, Clone)]
pub struct LogStats {
    bytes_served: u64,
    request_count: u64,
    cache_hits: u64,
}

type StatsMap = Arc<Mutex<HashMap<String, LogStats>>>;

type ProxyState = (
    Arc<Mutex<LruCache<String, Vec<u8>>>>, // Cache tracker
    String,                                // Target host
    Client,                                // HTTP client
    PathBuf,                               // Log directory
    String,                                // Log name
    StatsMap,                              // Statistics tracker
);

#[cfg(test)]
mod e2e_test;

#[derive(Debug, Deserialize)]
struct Config {
    scraper_contact_email: String,
    data_dir: String,
    torrent_dir: String,
    https_port: Option<u16>,
    http_port: Option<u16>,
    tls_cert: Option<String>,
    tls_key: Option<String>,
    logs: Vec<LogConfig>,
}

#[derive(Debug, Deserialize)]
struct LogConfig {
    name: String,
    log_url: String,
}

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to config YAML file
    #[arg(long, default_value = "config.yaml")]
    config_file: String,
    /// Enable verbose logging
    #[arg(long)]
    verbose: bool,
}

#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let args = Args::parse();
    let log_level = if args.verbose { "debug" } else { "info" };

    tracing_subscriber::fmt()
        .with_env_filter(log_level)
        .try_init()
        .unwrap();

    let config_content = match fs::read_to_string(&args.config_file).await {
        Ok(content) => content,
        Err(e) => {
            error!("Failed to read {}: {}", args.config_file, e);
            std::process::exit(1);
        }
    };

    let config: Config = match serde_yaml::from_str(&config_content) {
        Ok(config) => config,
        Err(e) => {
            error!("Failed to parse {}: {}", args.config_file, e);
            std::process::exit(1);
        }
    };

    if let Err(e) = launch_proxy(config).await {
        error!("Failed to launch proxy: {}", e);
        std::process::exit(1);
    }
}

async fn launch_proxy(config: Config) -> Result<(), Box<dyn std::error::Error>> {
    if config.http_port.is_none() && config.https_port.is_none() {
        let err_msg = "Neither http_port nor https_port is set in the config.";
        error!("{}", err_msg);
        return Err(err_msg.into());
    }

    let data_dir = PathBuf::from(&config.data_dir);
    if !data_dir.exists() {
        let err_msg = format!("Data directory does not exist: {}", data_dir.display());
        error!("{}", err_msg);
        return Err(err_msg.into());
    }

    let torrent_dir = PathBuf::from(&config.torrent_dir);
    if !torrent_dir.exists() {
        let err_msg = format!(
            "Torrent directory does not exist: {}",
            torrent_dir.display()
        );
        error!("{}", err_msg);
        return Err(err_msg.into());
    }

    let user_agent = format!(
        "Heliotorrent v0.0.1 scraper-contact:{}",
        &config.scraper_contact_email
    );
    let client = Client::builder()
        .user_agent(user_agent)
        .gzip(true)
        .pool_idle_timeout(Some(std::time::Duration::from_secs(600)))
        .pool_max_idle_per_host(10)
        .tcp_keepalive(Some(std::time::Duration::from_secs(60)))
        .build()
        .unwrap();

    let mut log_caches = Vec::new();
    for log in &config.logs {
        let log_dir = data_dir.join(&log.name);
        if !log_dir.exists() {
            let err_msg = format!("Log directory does not exist: {}", log_dir.display());
            error!("{}", err_msg);
            return Err(err_msg.into());
        }

        let lru_cache = Arc::new(Mutex::new(LruCache::new(NonZeroUsize::new(1024).unwrap())));

        log_caches.push((
            lru_cache,
            log.log_url.clone(),
            client.clone(),
            log_dir,
            log.name.clone(),
            Arc::new(Mutex::new(HashMap::new())),
        ));
    }

    // Create the router
    let app = create_multi_router(log_caches, config.torrent_dir);

    let mut handles = vec![];

    if let Some(http_port) = config.http_port {
        let http_addr = SocketAddr::new(IpAddr::from(Ipv6Addr::UNSPECIFIED), http_port);
        info!("Starting HTTP server on {}.", http_addr);
        let http_server = axum_server::bind(http_addr).serve(app.clone().into_make_service());
        handles.push(tokio::spawn(http_server));
    }

    if let Some(https_port) = config.https_port {
        if let (Some(cert_path), Some(key_path)) = (config.tls_cert, config.tls_key) {
            let https_addr = SocketAddr::new(IpAddr::from(Ipv6Addr::UNSPECIFIED), https_port);
            info!("HTTPS enabled. Starting HTTPS server on {}.", https_addr);
            rustls::crypto::aws_lc_rs::default_provider()
                .install_default()
                .unwrap();
            let certs = {
                let cert_file = &mut BufReader::new(std::fs::File::open(cert_path)?);
                certs(cert_file).collect::<Result<Vec<_>, _>>()?
            };
            let key = {
                let key_file = &mut BufReader::new(std::fs::File::open(key_path)?);
                private_key(key_file)?.ok_or("No private key found in key file")?
            };

            let tls_config = rustls::ServerConfig::builder()
                .with_no_client_auth()
                .with_single_cert(certs, key)?;

            let tls_config = RustlsConfig::from_config(Arc::new(tls_config));

            let https_server = axum_server::bind_rustls(https_addr, tls_config)
                .serve(app.clone().into_make_service());
            handles.push(tokio::spawn(https_server));
        } else {
            warn!(
                "https_port is set, but tls_cert or tls_key is missing. HTTPS server will not be started."
            );
        }
    }

    if handles.is_empty() {
        let err_msg = "No servers were started. Check your configuration.";
        error!("{}", err_msg);
        return Err(err_msg.into());
    }

    let (first_result, _, remaining_handles) = futures::future::select_all(handles).await;

    for handle in remaining_handles {
        handle.abort();
    }

    first_result?.map_err(|e| e.into())
}

pub fn create_multi_router(log_caches: Vec<ProxyState>, static_dir: String) -> Router {
    let mut app = Router::new();
    let stats = Arc::new(Mutex::new(HashMap::new()));

    let mut webseed_router = Router::new();
    for (cache_tracker, target_host, client, cache_dir, name, _) in &log_caches {
        let log_router = Router::new()
            .route("/*path", get(proxy_handler))
            .with_state((
                cache_tracker.clone(),
                target_host.clone(),
                client.clone(),
                cache_dir.clone(),
                name.clone(),
                stats.clone(),
            ));

        webseed_router = webseed_router.nest(&format!("/{}", name), log_router);
    }
    app = app.nest("/webseed", webseed_router);

    // Add statistics endpoint
    app = app.route("/statistics", get(statistics_handler).with_state(stats));

    // Add static file serving if directory is provided
    info!(
        "Serving static files at /torrents, disk path: {}",
        static_dir
    );
    app = app.nest_service("/torrents", ServeDir::new(static_dir));

    app
}

fn format_number(num: u64) -> String {
    let num_str = num.to_string();
    let mut result = String::new();
    let len = num_str.len();

    for (i, c) in num_str.chars().enumerate() {
        if i > 0 && (len - i).is_multiple_of(3) {
            result.push(',');
        }
        result.push(c);
    }
    result
}

fn format_bytes(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;
    const TB: u64 = GB * 1024;

    if bytes < KB {
        format!("{} bytes", bytes)
    } else if bytes < MB {
        format!("{:.2} KB", bytes as f64 / KB as f64)
    } else if bytes < GB {
        format!("{:.2} MB", bytes as f64 / MB as f64)
    } else if bytes < TB {
        format!("{:.2} GB", bytes as f64 / GB as f64)
    } else {
        format!("{:.2} TB", bytes as f64 / TB as f64)
    }
}

async fn statistics_handler(State(stats): axum::extract::State<StatsMap>) -> impl IntoResponse {
    let stats_guard = stats.lock().await;

    let mut stats_html = String::new();
    for (name, stats) in stats_guard.iter() {
        stats_html.push_str(&format!("<h2>{}</h2>\n", name));
        stats_html.push_str("<ul>\n");
        stats_html.push_str(&format!(
            "<li>Bytes served: {}</li>\n",
            format_bytes(stats.bytes_served)
        ));
        stats_html.push_str(&format!(
            "<li>Requests: {}</li>\n",
            format_number(stats.request_count)
        ));
        stats_html.push_str(&format!(
            "<li>Cache hit rate: {:.1}%</li>\n",
            if stats.request_count > 0 {
                (stats.cache_hits as f64 / stats.request_count as f64) * 100.0
            } else {
                0.0
            }
        ));
        stats_html.push_str("</ul>\n");
    }

    let html = format!(
        r#"<!DOCTYPE html>
<html>
<head>
    <title>Heliostat Statistics</title>
    <style>
        body {{ font-family: system-ui, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1, h2 {{ color: #333; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        ul {{ list-style-type: none; padding-left: 20px; }}
    </style>
</head>
<body>
    <h1>Log Statistics</h1>
    <p>This page shows the bytes served to BitTorrent clients since Heliostat's last restart.</p>
    {stats_html}
    <p><a href="/torrents">Back to Home</a></p>
</body>
</html>"#
    );

    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "text/html; charset=UTF-8")
        .body(Body::from(html))
        .unwrap()
}

#[instrument(skip(headers, state))]
async fn proxy_handler(
    Path(path): Path<String>,
    headers: HeaderMap,
    state: axum::extract::State<ProxyState>,
) -> axum::response::Response {
    let (cache, log_url, client, log_data_dir, name, stats) = &*state;

    // Update request count
    {
        let mut stats_guard = stats.lock().await;
        let log_stats = stats_guard.entry(name.clone()).or_default();
        log_stats.request_count += 1;
    }

    let path = sanitize_path(&path);

    if path.is_empty() {
        error!("Invalid path - empty after sanitization.");
        return StatusCode::BAD_REQUEST.into_response();
    }

    if path == "README.md" {
        return handle_readme(log_data_dir, &headers, name, stats).await;
    }

    let cache_key = path.clone();
    let mut is_cache_hit = false;

    let mut body = get_cached_body(cache, &cache_key).await;
    if body.is_some() {
        is_cache_hit = true;
        // Update cache hit count
        let mut stats_guard = stats.lock().await;
        let log_stats = stats_guard.entry(name.clone()).or_default();
        log_stats.cache_hits += 1;
    } else {
        body = fetch_and_cache_body(client, cache, log_url, &path, &cache_key).await;
    }

    let body = match body {
        Some(b) => b,
        None => return StatusCode::BAD_GATEWAY.into_response(),
    };

    // Check for range request
    if let Some(range_header) = headers.get(header::RANGE)
        && let Ok(range_str) = range_header.to_str()
        && let Some(resp) = handle_range_response(&body, range_str, is_cache_hit, name, stats).await
    {
        return resp;
    }

    // Update bytes served
    {
        let mut stats_guard = stats.lock().await;
        let log_stats = stats_guard.entry(name.clone()).or_default();
        log_stats.bytes_served += body.len() as u64;
    }

    //TODO: Why are the emitted Client Hello's only TLS1.2 and not using ALPN or HTTP2?

    debug!("Serving full response");
    let mut response = Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_LENGTH, body.len());

    if is_cache_hit {
        response = response.header("X-Cache", "HIT");
    } else {
        response = response.header("X-Cache", "MISS");
    }

    response.body(Body::from(body)).unwrap()
}

async fn handle_readme(
    cache_dir: &std::path::Path,
    headers: &HeaderMap,
    log_name: &str,
    stats: &StatsMap,
) -> axum::response::Response {
    let readme_path = cache_dir.join("README.md");
    debug!("Serving special README.md from {}", readme_path.display());

    match fs::read(&readme_path).await {
        Ok(body) => {
            if let Some(range_header) = headers.get(header::RANGE)
                && let Ok(range_str) = range_header.to_str()
                && let Some(resp) =
                    handle_range_response(&body, range_str, true, log_name, stats).await
            {
                return resp;
            }

            // Update bytes served
            {
                let mut stats_guard = stats.lock().await;
                let log_stats = stats_guard.entry(log_name.to_string()).or_default();
                log_stats.bytes_served += body.len() as u64;
            }

            debug!("Serving full README.md");
            Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, "text/markdown; charset=UTF-8")
                .header(header::CONTENT_LENGTH, body.len())
                .body(Body::from(body))
                .unwrap()
        }
        Err(e) => {
            error!(
                "Failed to read special README.md from {:?}: {}",
                readme_path, e
            );
            StatusCode::NOT_FOUND.into_response()
        }
    }
}

fn sanitize_path(path: &str) -> String {
    let parts: Vec<&str> = path.splitn(2, '/').collect();
    let result = if parts.len() > 1 {
        let raw = parts[1];
        use std::path::{Component, Path};
        let mut sanitized = Vec::new();
        let mut valid = true;
        for comp in Path::new(raw).components() {
            match comp {
                Component::Normal(seg) => sanitized.push(seg.to_string_lossy()),
                _ => {
                    valid = false;
                    break;
                }
            }
        }
        if !valid || sanitized.is_empty() {
            error!("Invalid path - contains non-normal components: {}", raw);
            String::new()
        } else {
            sanitized.join("/")
        }
    } else {
        String::new()
    };
    debug!("Sanitized path: {}", result);
    result
}

async fn get_cached_body(
    cache: &Arc<Mutex<LruCache<String, Vec<u8>>>>,
    cache_key: &str,
) -> Option<Vec<u8>> {
    let mut cache_guard = cache.lock().await;
    cache_guard.get(cache_key).cloned()
}

async fn fetch_and_cache_body(
    client: &Client,
    cache: &Arc<Mutex<LruCache<String, Vec<u8>>>>,
    target_host: &str,
    final_path: &str,
    cache_key: &str,
) -> Option<Vec<u8>> {
    let target_url = {
        let base = target_host.trim_end_matches('/');
        let path = final_path.trim_start_matches('/');
        format!("{base}/{path}")
    };
    debug!(target_url = %target_url, "Fetching full file from upstream");

    //TODO Not sure if this is reusing connections properly.
    let resp = match client.get(&target_url).send().await {
        Ok(r) => r,
        Err(e) => {
            error!("Request to upstream failed: {}", e);
            return None;
        }
    };

    if !resp.status().is_success() {
        error!("Upstream responded with error status: {}", resp.status());
        return None;
    }

    let body = match resp.bytes().await {
        Ok(b) => b.to_vec(),
        Err(e) => {
            error!("Failed to read response body: {}", e);
            return None;
        }
    };

    let mut cache_guard = cache.lock().await;
    cache_guard.put(cache_key.to_string(), body.clone());
    debug!("Cached full response");
    Some(body)
}

async fn handle_range_response(
    body: &[u8],
    range_str: &str,
    is_cache_hit: bool,
    log_name: &str,
    stats: &StatsMap,
) -> Option<Response<Body>> {
    if let Some((start, end)) = parse_range_header(range_str, body.len()) {
        debug!(
            start = start,
            end = end - 1,
            total = body.len(),
            "Serving byte range"
        );
        if start >= body.len() || end > body.len() || start >= end {
            warn!(
                "Invalid range request: start={}, end={}, body_length={}",
                start,
                end,
                body.len()
            );
            return Some(
                Response::builder()
                    .status(StatusCode::RANGE_NOT_SATISFIABLE)
                    .body(Body::empty())
                    .unwrap(),
            );
        }

        let partial = &body[start..end];

        // Update bytes served for this range
        {
            let mut stats_guard = stats.lock().await;
            let log_stats = stats_guard.entry(log_name.to_string()).or_default();
            log_stats.bytes_served += partial.len() as u64;
        }

        let mut response = Response::builder()
            .status(StatusCode::PARTIAL_CONTENT)
            .header(
                header::CONTENT_RANGE,
                format!("bytes {}-{}/{}", start, end - 1, body.len()),
            )
            .header(header::CONTENT_LENGTH, partial.len());

        if is_cache_hit {
            response = response.header("X-Cache", "HIT");
        } else {
            response = response.header("X-Cache", "MISS");
        }

        return Some(response.body(Body::from(partial.to_vec())).unwrap());
    }
    None
}

fn parse_range_header(range: &str, len: usize) -> Option<(usize, usize)> {
    if !range.starts_with("bytes=") {
        return None;
    }
    let range = &range[6..];
    let parts: Vec<&str> = range.split('-').collect();
    if parts.len() != 2 {
        return None;
    }
    let start = parts[0].parse::<usize>().ok()?;
    let end = if parts[1].is_empty() {
        len
    } else {
        parts[1].parse::<usize>().ok()? + 1
    };
    Some((start, end))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_load_config_yaml() {
        let yaml = fs::read_to_string("test/test_config.yaml").expect("test_config.yaml missing");
        let _: Config = serde_yaml::from_str(&yaml).unwrap();
    }
}
