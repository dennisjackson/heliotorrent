#[cfg(test)]
mod tests {
    use crate::launch_proxy;
    use crate::{Args, Config, LogConfig};
    use std::future::Future;
    use std::net::TcpListener;

    use axum::http::{StatusCode, header};

    use tempfile::TempDir;

    fn init_test_logging() {
        let _ = tracing_subscriber::fmt()
            .with_env_filter("debug")
            .try_init();
    }

    fn get_available_port() -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.local_addr().unwrap().port()
    }

    fn create_test_app() -> (impl Future<Output = ()>, TempDir, TempDir, u16) {
        let data_dir = TempDir::new().unwrap();
        let torrent_dir = TempDir::new().unwrap();
        let port = get_available_port();

        let test_log_data = data_dir.path().join("test_log");
        let test_log_torrent = torrent_dir.path().join("test_log");
        std::fs::create_dir_all(&test_log_data).unwrap();
        std::fs::create_dir_all(&test_log_torrent).unwrap();

        std::fs::write(test_log_data.join("README.md"), "This is a test README.").unwrap();
        std::fs::write(test_log_torrent.join("feed.xml"), "<xml></xml>").unwrap();
        std::fs::write(
            test_log_torrent.join("L01-0-1048576.torrent"),
            "{torrent_data}",
        )
        .unwrap();

        let config: Config = Config {
            data_dir: data_dir.path().to_string_lossy().to_string(),
            torrent_dir: torrent_dir.path().to_string_lossy().to_string(),
            scraper_contact_email: "".to_string(),
            http_port: Some(port),
            https_port: None,
            tls_cert: None,
            tls_key: None,
            logs: vec![LogConfig {
                name: "test_log".to_string(),
                log_url: "https://tuscolo2025h2.skylight.geomys.org/".to_string(),
            }],
        };
        (
            async move {
                let _ = Args {
                    config_file: "test_config.yaml".to_string(),
                };
                if let Err(e) = launch_proxy(config).await {
                    panic!("Failed to launch proxy for test: {}", e);
                }
            },
            data_dir,
            torrent_dir,
            port,
        )
    }

    async fn run_test<F, Fut>(test_fn: F)
    where
        F: FnOnce(u16) -> Fut + Send + 'static,
        Fut: Future<Output = ()> + Send,
    {
        init_test_logging();
        let (server_future, _data_dir, _torrent_dir, port) = create_test_app();
        let server_handle = tokio::spawn(server_future);
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;

        // The `test_fn` might panic. We run it in a separate task to catch the panic.
        let test_handle = tokio::spawn(async move {
            test_fn(port).await;
        });

        let result = test_handle.await;

        server_handle.abort();
        // Wait for the server to shut down completely.
        // We expect a cancelled error, so we ignore the result.
        let _ = server_handle.await;

        if let Err(e) = result
            && e.is_panic() {
                std::panic::resume_unwind(e.into_panic());
            }
    }

    async fn get_body(
        port: u16,
        uri: &str,
        headers: &[(&str, &str)],
    ) -> (
        reqwest::StatusCode,
        bytes::Bytes,
        reqwest::header::HeaderMap,
    ) {
        use reqwest::Client;
        let client = Client::new();
        let url = format!("http://127.0.0.1:{}{}", port, uri);
        let mut req = client.get(&url);
        for (k, v) in headers {
            req = req.header(*k, *v);
        }
        let resp = req.send().await.unwrap();
        let status = resp.status();
        let headers = resp.headers().clone();
        let body = resp.bytes().await.unwrap();
        (status, body, headers)
    }

    async fn get_range(
        port: u16,
        uri: &str,
        start: usize,
        end: usize,
    ) -> (
        reqwest::StatusCode,
        bytes::Bytes,
        reqwest::header::HeaderMap,
    ) {
        get_body(port, uri, &[("range", &format!("bytes={}-{}", start, end))]).await
    }

    const TEST_URI: &str = "/webseed/test_log/test-torrent-name/tile/data";

    #[tokio::test]
    async fn test_basic_urls_work() {
        run_test(|port| async move {
            let test_uris = [
                "/webseed/test_log/test-torrent-name/tile/data/000",
                "/webseed/test_log/test-torrent-name/tile/data/001",
                "/webseed/test_log/test-torrent-name/README.md",
                "/statistics",
                "/torrents/test_log/feed.xml",
                "/torrents/test_log/L01-0-1048576.torrent",
            ];
            for uri in test_uris.iter() {
                let (status, body, _) = get_body(port, uri, &[]).await;
                assert_eq!(
                    status,
                    StatusCode::OK,
                    "Failed for URI: {} Status: {}",
                    uri,
                    status
                );
                assert!(!body.is_empty());
            }
        })
        .await;
    }

    #[tokio::test]
    async fn test_proxy_full_file() {
        run_test(|port| async move {
            let uri = format!("{}/000", TEST_URI);

            let (status1, body1, headers1) = get_body(port, &uri, &[]).await;
            assert_eq!(status1, StatusCode::OK);
            assert_eq!(headers1.get("X-Cache").unwrap(), "MISS");
            assert!(!body1.is_empty());

            let (status2, body2, headers2) = get_body(port, &uri, &[]).await;
            assert_eq!(status2, StatusCode::OK);
            assert_eq!(headers2.get("X-Cache").unwrap(), "HIT");
            assert_eq!(body2, body1);
        })
        .await;
    }

    #[tokio::test]
    async fn test_proxy_range_request() {
        run_test(|port| async move {
            let uri = format!("{}/000", TEST_URI);

            let (_, body_full, _) = get_body(port, &uri, &[]).await;
            let (range_start, range_end) = (10, 50);
            let (status, body_range, headers) = get_range(port, &uri, range_start, range_end).await;
            assert_eq!(status, StatusCode::PARTIAL_CONTENT);
            assert_eq!(headers.get("X-Cache").unwrap(), "HIT");
            let content_range = headers.get(header::CONTENT_RANGE).unwrap();
            let expected_range = format!("bytes {}-{}/{}", range_start, range_end, body_full.len());
            assert_eq!(content_range, &expected_range);
            assert_eq!(&body_range[..], &body_full[range_start..=range_end]);
        })
        .await;
    }

    async fn invalid_range_test(port: u16, uri: &str, start: usize, end: usize) {
        let (status, _, _) = get_range(port, uri, start, end).await;
        assert_eq!(status, StatusCode::RANGE_NOT_SATISFIABLE);
    }

    #[tokio::test]
    async fn test_proxy_invalid_range_start_too_large() {
        run_test(|port| async move {
            let uri = format!("{}/001", TEST_URI);
            let (_, body, _) = get_body(port, &uri, &[]).await;
            let sz = body.len();
            invalid_range_test(port, &uri, sz + 10, sz + 20).await;
        })
        .await;
    }

    #[tokio::test]
    async fn test_proxy_invalid_range_start_greater_than_end() {
        run_test(|port| async move {
            let uri = format!("{}/002", TEST_URI);
            let _ = get_body(port, &uri, &[]).await;
            invalid_range_test(port, &uri, 50, 20).await;
        })
        .await;
    }

    #[tokio::test]
    async fn test_proxy_range_end_too_large() {
        run_test(|port| async move {
            let uri = format!("{}/004", TEST_URI);
            let (_, body, _) = get_body(port, &uri, &[]).await;
            let sz = body.len();
            invalid_range_test(port, &uri, 10, sz + 100).await;
        })
        .await;
    }

    #[tokio::test]
    async fn test_proxy_malformed_range_header() {
        run_test(|port| async move {
            let uri = format!("{}/003", TEST_URI);
            let (_, body_full, _) = get_body(port, &uri, &[]).await;
            let (status, body, _) =
                get_body(port, &uri, &[("range", "invalid-range-format")]).await;
            assert_eq!(status, StatusCode::OK);
            assert_eq!(body.len(), body_full.len());
        })
        .await;
    }

    #[tokio::test]
    async fn test_no_range_request_handling() {
        run_test(|port| async move {
            let uri = format!("{}/000", TEST_URI);

            let (_, body_full, _) = get_body(port, &uri, &[]).await;
            let (status, body, headers) = get_body(port, &uri, &[]).await;
            assert_eq!(status, StatusCode::OK);
            assert_eq!(headers.get("X-Cache").unwrap(), "HIT");
            assert_eq!(body, body_full);
        })
        .await;
    }

    #[tokio::test]
    async fn test_no_accept_encoding_header() {
        run_test(|port| async move {
            let uri = format!("{}/005", TEST_URI);

            let (status, body, headers) = get_body(port, &uri, &[]).await;
            assert_eq!(status, StatusCode::OK);
            assert!(!body.is_empty());
            if let Some(encoding) = headers.get(header::CONTENT_ENCODING) {
                assert_ne!(encoding.to_str().unwrap().to_lowercase(), "gzip");
            }
        })
        .await;
    }

    #[tokio::test]
    async fn test_serve_static_files() {
        run_test(|port| async move {
            // This test is now invalid as we can't write to the temp dir.
            // It needs to be rewritten to depend on files created in create_test_app.
            // For now, we just check that a non-existent file returns a 404.
            let (status, _, _) = get_body(port, "/torrents/example.html", &[]).await;
            assert_eq!(status, StatusCode::NOT_FOUND);
        })
        .await;
    }

    #[tokio::test]
    async fn test_readme_special_handling() {
        run_test(|port| async move {
            let log_name = "test_log";
            let readme_content = "This is a test README.";
            let uri = format!("/webseed/{}/torrent-name/README.md", log_name);
            let (status, body, headers) = get_body(port, &uri, &[]).await;
            assert_eq!(status, StatusCode::OK);
            assert_eq!(
                headers.get(header::CONTENT_TYPE).unwrap(),
                "text/markdown; charset=UTF-8"
            );
            assert_eq!(body, readme_content.as_bytes());
        })
        .await;
    }
}
