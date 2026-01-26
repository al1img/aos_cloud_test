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
        return "Convert items to OCI blobs"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Convert items to OCI blobs based on config.yaml.

        Args:
            args: Command arguments (none expected)
            context: Context with server references
        """
        config = context.get("config", {})
        items_path = config.get("itemsPath", "./items")
        root_directory = config.get("fileServer", {}).get("rootDirectory", "./files")

        # Create sha256 directory for blobs
        sha256_dir = os.path.join(root_directory, "sha256")
        os.makedirs(sha256_dir, exist_ok=True)

        # Process items
        if not os.path.exists(items_path):
            raise FileNotFoundError(f"Items path not found: {items_path}")

        items_processed = 0
        blobs_created = 0
        item_index_digests = {}  # Map item ID to index digest

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
            blobs_count, index_digests = await self._process_item(item_config, item_dir, sha256_dir)

            blobs_created += blobs_count
            items_processed += 1

            # Store index digests by item IDs
            item_index_digests.update(index_digests)

            print("\nUpdate complete:")
            print(f"  Items processed: {items_processed}")
            print(f"  Blobs created: {blobs_created}")

            logging.info("Update complete: %d items, %d blobs", items_processed, blobs_created)

        # Update messages with index digests
        messages_path = config.get("messagesPath", "./messages")

        if os.path.exists(messages_path):
            await self._update_messages(messages_path, item_index_digests)

        else:
            logging.warning("Messages path not found: %s", messages_path)

    def _calculate_file_checksum(self, file_path: str, chunk_size: int = 1024 * 1024) -> str:
        """Calculate SHA256 checksum of a file by reading it in chunks.

        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read (default 1MB)

        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)

                if not chunk:
                    break

                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    async def _update_messages(self, messages_path: str, item_index_digests: Dict[str, str]):
        """Update message files with index digests for matching items.

        Args:
            messages_path: Path to messages directory
            item_index_digests: Map of item ID to index digest
        """
        if not item_index_digests:
            logging.info("No item index digests to update in messages")

            return

        for message_file in os.listdir(messages_path):
            if not message_file.endswith(".json"):
                continue

            message_path = os.path.join(messages_path, message_file)

            logging.info("Process message file: %s", message_file)

            with open(message_path, "r", encoding="utf-8") as f:
                message_data = json.load(f)

            # Check if this is a desiredStatus message
            if message_data.get("messageType") != "desiredStatus":
                logging.info("Skip message %s: not a desiredStatus message", message_file)

                continue

            # Update indexDigest for matching items
            updated = False

            for item in message_data.get("items", []):
                item_info = item.get("item", {})
                item_id = item_info.get("id")

                if item_id in item_index_digests:
                    old_digest = item.get("indexDigest")
                    new_digest = item_index_digests[item_id]

                    item["indexDigest"] = new_digest
                    updated = True

                    logging.info(
                        "Update indexDigest for item %s: %s -> %s",
                        item_id,
                        old_digest,
                        new_digest,
                    )

            # Write updated message if changes were made
            if updated:
                with open(message_path, "w", encoding="utf-8") as f:
                    json.dump(message_data, f, indent=4, ensure_ascii=False)

                logging.info("Update message file: %s", message_file)

                print(f"Updated message: {message_file}")

    async def _process_item(self, item_config: dict, item_dir: str, sha256_dir: str) -> tuple[int, Dict[str, str]]:
        """
        Process a single item based on config.yaml.

        Args:
            item_config: Parsed config.yaml content
            item_dir: Path to item directory
            sha256_dir: Directory to store blobs

        Returns:
            Tuple of (number of blobs created, dict of item IDs to index digest)
        """
        blobs_created = 0
        item_id_map = {}

        # Process each item in the configuration
        for item in item_config.get("items", []):
            item_id = item.get("identity", {}).get("id")
            images = item.get("images", [])
            configuration = item.get("configuration", {})
            manifest_entries = []

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
                image_config = self._create_image_config(image, configuration, diff_ids)
                image_config_hash, image_config_size = await self._deploy_spec(image_config, sha256_dir)

                logging.info("Create image config blob: %s", image_config_hash)

                blobs_created += 1

                # Create service config
                service_config = self._create_service_config(configuration)
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

            # Create index for this item
            index_data = {"schemaVersion": 2, "manifests": manifest_entries}

            index_hash, _ = await self._deploy_spec(index_data, sha256_dir)

            logging.info("Deploy index blob: %s for item %s", index_hash, item_id)

            blobs_created += 1

            # Store index digest for this item
            if item_id:
                item_id_map[item_id] = f"sha256:{index_hash}"

        return blobs_created, item_id_map

    def _create_image_config(self, image: dict, configuration: dict = None, diff_ids: List[str] = None) -> dict:
        """
        Create image config JSON from config.yaml data.

        Args:
            image: Image configuration from config.yaml
            configuration: Configuration section from config.yaml
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

        # Add exposed ports if specified in configuration
        if configuration:
            if "exposedPorts" in configuration:
                exposed_ports = configuration["exposedPorts"]

                if exposed_ports:
                    exposed_ports_dict = {}

                    for port_spec in exposed_ports:
                        # Port spec can be like "8089-8090/tcp", "1515/udp", or "9000"
                        port_str = str(port_spec)

                        exposed_ports_dict[port_str] = {}

                    image_config["config"]["ExposedPorts"] = exposed_ports_dict

        # Add rootfs with diff_ids
        if diff_ids:
            image_config["rootfs"] = {"diff_ids": diff_ids, "type": "layers"}

        return image_config

    def _create_service_config(self, configuration: dict = None) -> dict:
        """
        Create service config JSON from config.yaml data.

        Args:
            configuration: Configuration section from config.yaml

        Returns:
            Service config dictionary
        """

        service_config = {}

        # Add hostname if specified
        if "hostname" in configuration:
            service_config["hostname"] = configuration["hostname"]

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

        # Add allowed connections if specified
        if "allowedConnections" in configuration:
            allowed_connections = configuration["allowedConnections"]

            if allowed_connections:
                allowed_connections_dict = {}

                for connection_spec in allowed_connections:
                    # Connection spec is like "service-UUID/8087-8088/tcp" or "service-UUID/1515/udp"
                    connection_str = str(connection_spec)

                    allowed_connections_dict[connection_str] = {}

                service_config["allowedConnections"] = allowed_connections_dict

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

            # Gzip the uncompressed tar (mtime=0 for deterministic output)
            compressed_content = gzip.compress(uncompressed_content, mtime=0)

            # Calculate SHA256 of compressed content
            sha256_hash = hashlib.sha256(compressed_content).hexdigest()
            blob_size = len(compressed_content)

            # Check if blob already exists with correct checksum
            blob_path = os.path.join(dst_dir, sha256_hash)

            if os.path.exists(blob_path):
                # Verify existing blob checksum by reading in chunks
                existing_hash = self._calculate_file_checksum(blob_path)

                if existing_hash == sha256_hash:
                    logging.info("Blob %s already exists with correct checksum, skip writing", sha256_hash)

                    return sha256_hash, uncompressed_hash, blob_size

                logging.warning("Blob %s exists but has incorrect checksum, overwrite", sha256_hash)

            # Write blob
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

        # Check if blob already exists with correct checksum
        blob_path = os.path.join(dst_dir, sha256_hash)

        if os.path.exists(blob_path):
            # Verify existing blob checksum by reading in chunks
            existing_hash = self._calculate_file_checksum(blob_path)

            if existing_hash == sha256_hash:
                logging.info("Blob %s already exists with correct checksum, skip writing", sha256_hash)

                return sha256_hash, blob_size

            logging.warning("Blob %s exists but has incorrect checksum, overwrite", sha256_hash)

        # Write blob
        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size
