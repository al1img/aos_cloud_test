"""Update command implementation."""

import datetime
import gzip
import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
from typing import Any, Dict, List

import yaml

from .base import Command


class UpdateCommand(Command):
    """Update OCI blobs from items."""

    @property
    def name(self) -> str:
        return "update"

    @property
    def help_args(self) -> str:
        return ""

    @property
    def help(self) -> str:
        return "Clear file server and convert items to OCI blobs"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Clear file server root directory and convert items to OCI blobs based on config.yaml.

        Args:
            args: Command arguments (none expected)
            context: Context with server references
        """
        config = context.get("config", {})
        items_path = config.get("itemsPath", "./items")
        root_directory = config.get("fileServer", {}).get("rootDirectory", "./files")

        logging.info("Clear file server root directory: %s", root_directory)

        if os.path.exists(root_directory):
            shutil.rmtree(root_directory)

        # Create sha256 directory for blobs
        sha256_dir = os.path.join(root_directory, "sha256")
        os.makedirs(sha256_dir, exist_ok=True)

        # Process items
        if not os.path.exists(items_path):
            raise FileNotFoundError(f"Items path not found: {items_path}")

        items_processed = 0
        blobs_created = 0

        for item_name in os.listdir(items_path):
            item_dir = os.path.join(items_path, item_name)

            if not os.path.isdir(item_dir):
                continue

            logging.info("Process item: %s", item_name)

            print(f"Processing item: {item_name}")

            # Read config.yaml
            config_yaml_path = os.path.join(item_dir, "config.yaml")

            if not os.path.exists(config_yaml_path):
                logging.warning("Skip item %s: config.yaml not found", item_name)

                continue

            with open(config_yaml_path, "r", encoding="utf-8") as f:
                item_config = yaml.safe_load(f)

            # Generate JSON files and blobs from config.yaml
            blobs_count = await self._process_item(item_config, item_dir, sha256_dir)

            blobs_created += blobs_count
            items_processed += 1

            print("\nUpdate complete:")
            print(f"  Items processed: {items_processed}")
            print(f"  Blobs created: {blobs_created}")

            logging.info("Update complete: %d items, %d blobs", items_processed, blobs_created)

    async def _process_item(self, item_config: dict, item_dir: str, sha256_dir: str) -> int:
        """
        Process a single item based on config.yaml.

        Args:
            item_config: Parsed config.yaml content
            item_dir: Path to item directory
            sha256_dir: Directory to store blobs

        Returns:
            Number of blobs created
        """
        blobs_created = 0
        manifest_entries = []

        # Process each item in the configuration
        for item in item_config.get("items", []):
            images = item.get("images", [])
            configuration = item.get("configuration", {})

            # Process each image in the item
            for image in images:
                diff_ids = []
                manifest_layers = []

                # Process rootfs layers
                source_folder = image.get("source_folder", "rootfs")
                layer_path = os.path.join(item_dir, source_folder)

                if os.path.exists(layer_path) and os.path.isdir(layer_path):
                    blob_hash, uncompressed_hash, blob_size = await self._deploy_layer_blob(layer_path, sha256_dir)

                    logging.info("Create layer blob: %s (uncompressed: %s)", blob_hash, uncompressed_hash)

                    diff_ids.append(f"sha256:{uncompressed_hash}")

                    manifest_layers.append(
                        {
                            "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                            "digest": f"sha256:{blob_hash}",
                            "size": blob_size,
                        }
                    )

                    blobs_created += 1

                # Create image config
                image_config = self._create_image_config(image, item_config, diff_ids)
                image_config_hash, image_config_size = await self._deploy_spec(image_config, sha256_dir)

                logging.info("Create image config blob: %s", image_config_hash)

                blobs_created += 1

                # Create service config
                service_config = self._create_service_config(configuration, item_config)
                service_config_hash, service_config_size = await self._deploy_spec(service_config, sha256_dir)

                logging.info("Create service config blob: %s", service_config_hash)

                # Create manifest with proper key order
                manifest_data = {
                    "schemaVersion": 2,
                    "config": {
                        "mediaType": "application/vnd.oci.image.config.v1+json",
                        "digest": f"sha256:{image_config_hash}",
                        "size": image_config_size,
                    },
                    "aosService": {
                        "mediaType": "application/vnd.aos.service.config.v1+json",
                        "digest": f"sha256:{service_config_hash}",
                        "size": service_config_size,
                    },
                    "layers": manifest_layers,
                }

                blobs_created += 1

                # Deploy manifest
                manifest_hash, manifest_size = await self._deploy_spec(manifest_data, sha256_dir)

                logging.info("Deploy manifest blob: %s", manifest_hash)

                manifest_entries.append(
                    {
                        "mediaType": "application/vnd.oci.image.manifest.v1+json",
                        "digest": f"sha256:{manifest_hash}",
                        "size": manifest_size,
                    }
                )

                blobs_created += 1

        # Create index
        index_data = {"schemaVersion": 2, "manifests": manifest_entries}

        index_hash, _ = await self._deploy_spec(index_data, sha256_dir)

        logging.info("Deploy index blob: %s", index_hash)

        blobs_created += 1

        return blobs_created

    def _create_image_config(self, image: dict, item_config: dict, diff_ids: List[str]) -> dict:
        """
        Create image config JSON from config.yaml data.

        Args:
            image: Image configuration from config.yaml
            item_config: Full item configuration
            diff_ids: List of uncompressed layer digests

        Returns:
            Image config dictionary
        """
        os_info = image.get("os_info", {})
        arch_info = image.get("arch_info", {})

        image_config = {
            "architecture": arch_info.get("architecture", "amd64"),
            "os": os_info.get("os", "linux"),
            "config": {},
        }

        # Add command if specified
        if "cmd" in image:
            cmd = image["cmd"]

            if isinstance(cmd, list) and len(cmd) > 0:
                image_config["config"]["Entrypoint"] = [cmd[0]]

                if len(cmd) > 1:
                    image_config["config"]["Cmd"] = cmd[1:]

        # Add working directory if specified
        if "work_dir" in image:
            image_config["config"]["WorkingDir"] = image["work_dir"]

        # Add rootfs with diff_ids
        if diff_ids:
            image_config["rootfs"] = {"diff_ids": diff_ids, "type": "layers"}

        return image_config

    def _create_service_config(self, configuration: dict, item_config: dict) -> dict:
        """
        Create service config JSON from config.yaml data.

        Args:
            configuration: Configuration section from config.yaml
            item_config: Full item configuration

        Returns:
            Service config dictionary
        """
        publisher = item_config.get("publisher", {})
        author = publisher.get("author", "Unknown")

        service_config = {}

        # Add runtimes if specified
        if "runtimes" in configuration:
            service_config["runtimes"] = configuration["runtimes"]

        # Add quotas if specified
        if "quotas" in configuration:
            quotas = configuration["quotas"]
            service_quotas = {}

            if "cpu_limit" in quotas:
                service_quotas["cpuDmipsLimit"] = quotas["cpu_limit"]

            if "ram_limit" in quotas:
                service_quotas["ramLimit"] = quotas["ram_limit"]

            if "storage_limit" in quotas:
                service_quotas["storageLimit"] = quotas["storage_limit"]

            if service_quotas:
                service_config["quotas"] = service_quotas

        return service_config

    async def _deploy_layer_blob(self, dir_path: str, dst_dir: str) -> tuple[str, str, int]:
        """
        Create a compressed tar.gz blob from a directory.

        Args:
            dir_path: Path to source directory
            dst_dir: Directory to store blobs

        Returns:
            Tuple of (SHA256 hash, uncompressed hash, blob size in bytes)
        """
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_uncompressed:
            tmp_uncompressed_path = tmp_uncompressed.name

        try:
            # Create uncompressed tar archive
            with tarfile.open(tmp_uncompressed_path, "w") as tar:
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    tar.add(item_path, arcname=item)

            # Read uncompressed content and calculate hash
            with open(tmp_uncompressed_path, "rb") as f:
                uncompressed_content = f.read()

            uncompressed_hash = hashlib.sha256(uncompressed_content).hexdigest()

            # Gzip the uncompressed tar
            compressed_content = gzip.compress(uncompressed_content)

            # Calculate SHA256 of compressed content
            sha256_hash = hashlib.sha256(compressed_content).hexdigest()
            blob_size = len(compressed_content)

            # Write blob
            blob_path = os.path.join(dst_dir, sha256_hash)

            with open(blob_path, "wb") as f:
                f.write(compressed_content)

            return sha256_hash, uncompressed_hash, blob_size

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_uncompressed_path):
                os.remove(tmp_uncompressed_path)

    async def _deploy_spec(self, spec_data: dict, dst_dir: str) -> tuple[str, int]:
        """
        Deploy a spec by creating a blob from the modified spec.

        Args:
            spec_data: Modified spec dictionary
            dst_dir: Directory to store blobs

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        # Serialize manifest to JSON with proper formatting
        spec_json = json.dumps(spec_data, indent=4, ensure_ascii=False)
        content = spec_json.encode("utf-8")

        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        blob_size = len(content)

        # Write blob
        blob_path = os.path.join(dst_dir, sha256_hash)

        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size
