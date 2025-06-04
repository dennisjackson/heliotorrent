#!/usr/bin/env python3
"""
Cloudflare Pages Deployment Script

This script uses the Wrangler CLI tool to deploy a directory to Cloudflare Pages
while preserving the directory structure.
"""

import argparse
import logging
import os
import subprocess
import sys
import json
import tempfile
from typing import Dict, List, Optional

import coloredlogs


class WranglerDeployer:
    """Handles deploying to Cloudflare Pages using Wrangler CLI."""

    def __init__(
        self,
        project_name: str,
        directory: str,
        account_id: Optional[str] = None,
        production: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize the Wrangler deployer.

        Args:
            project_name: Cloudflare Pages project name
            directory: Directory to upload
            account_id: Cloudflare account ID (optional)
            production: Whether to deploy to production
            verbose: Whether to emit verbose logs
        """
        self.project_name = project_name
        self.directory = os.path.abspath(directory)
        self.account_id = account_id
        self.production = production
        
        # Set up logging
        log_level = "DEBUG" if verbose else "INFO"
        fmt = "%(asctime)s %(levelname)s: %(message)s"
        coloredlogs.install(level=log_level, fmt=fmt)
        
        # Check if wrangler is installed
        self._check_wrangler()

    def _check_wrangler(self) -> None:
        """Check if Wrangler CLI is installed."""
        try:
            result = subprocess.run(
                ["wrangler", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logging.error("Wrangler CLI not found or not working properly")
                logging.error("Install with: npm install -g wrangler")
                sys.exit(1)
            logging.debug(f"Found Wrangler: {result.stdout.strip()}")
        except FileNotFoundError:
            logging.error("Wrangler CLI not found")
            logging.error("Install with: npm install -g wrangler")
            sys.exit(1)

    def _check_login_status(self) -> bool:
        """Check if user is logged in to Cloudflare."""
        try:
            result = subprocess.run(
                ["wrangler", "whoami"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _create_temp_config(self) -> str:
        """
        Create a temporary wrangler.toml configuration file.
        
        Returns:
            Path to the temporary config file
        """
        config = {
            "name": self.project_name,
            "compatibility_date": "2023-01-01",
        }
        
        if self.account_id:
            config["account_id"] = self.account_id
            
        # Create a temporary directory for the config
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "wrangler.toml")
        
        # Write the config to a TOML file
        with open(config_path, "w") as f:
            f.write(f"name = \"{self.project_name}\"\n")
            f.write("compatibility_date = \"2023-01-01\"\n")
            if self.account_id:
                f.write(f"account_id = \"{self.account_id}\"\n")
        
        logging.debug(f"Created temporary config at {config_path}")
        return config_path

    def deploy(self) -> bool:
        """
        Deploy the directory to Cloudflare Pages.
        
        Returns:
            True if successful, False otherwise
        """
        # Validate directory exists
        if not os.path.isdir(self.directory):
            logging.error(f"Directory not found: {self.directory}")
            return False
            
        # Check if logged in
        if not self._check_login_status():
            logging.error("Not logged in to Cloudflare. Run 'wrangler login' first.")
            return False
            
        # Create temporary config
        config_path = self._create_temp_config()
        config_dir = os.path.dirname(config_path)
        
        # Build the deploy command
        cmd = ["wrangler", "pages", "deploy", self.directory]
        cmd.extend(["--project-name", self.project_name])
        
        if self.production:
            cmd.append("--production")
        else:
            cmd.append("--branch=preview")
            
        if self.account_id:
            cmd.extend(["--account-id", self.account_id])
            
        # Run the deploy command
        logging.info(f"Deploying {self.directory} to Cloudflare Pages project {self.project_name}")
        logging.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            # Change to the config directory so wrangler can find the config
            original_dir = os.getcwd()
            os.chdir(config_dir)
            
            # Run the deploy command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            
            # Stream the output
            deployment_url = None
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                # Try to extract the deployment URL
                if "https://" in line and ".pages.dev" in line:
                    parts = line.split("https://")
                    if len(parts) > 1:
                        url_part = parts[1].split()[0]
                        deployment_url = f"https://{url_part}"
            
            # Wait for the process to complete
            process.wait()
            
            # Change back to the original directory
            os.chdir(original_dir)
            
            # Check if deployment was successful
            if process.returncode == 0:
                logging.info("Deployment completed successfully")
                if deployment_url:
                    logging.info(f"Deployment URL: {deployment_url}")
                return True
            else:
                logging.error(f"Deployment failed with exit code {process.returncode}")
                return False
                
        except Exception as e:
            logging.error(f"Error during deployment: {e}")
            return False
        finally:
            # Clean up the temporary config
            try:
                os.remove(config_path)
                os.rmdir(config_dir)
            except:
                pass


def main():
    """Parse arguments and run the deployer."""
    parser = argparse.ArgumentParser(
        description="Deploy a directory to Cloudflare Pages using Wrangler",
        epilog="Example: ./cloudflare_pages_deploy.py --project-name my-site --directory ./public",
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Cloudflare Pages project name",
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="Directory to upload",
    )
    parser.add_argument(
        "--account-id",
        help="Cloudflare account ID (optional)",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Deploy to production (default is preview)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()
    
    # Create and run deployer
    deployer = WranglerDeployer(
        project_name=args.project_name,
        directory=args.directory,
        account_id=args.account_id,
        production=args.production,
        verbose=args.verbose,
    )
    
    success = deployer.deploy()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
