"""Update command implementation."""

import copy
import hashlib
import json
import logging
import os
import shutil
import tarfile
from typing import Any, Dict, List

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
        Clear file server root directory and convert items to OCI blobs.

        Args:
            args: Command arguments (none expected)
            context: Context with server references
        """
        config = context.get("config", {})
        items_path = config.get("itemsPath", "./items")
        root_directory = config.get("fileServer", {}).get("rootDirectory", "./files")

        # Clear root directory
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

            # Read index.json
            index_path = os.path.join(item_dir, "index.json")

            if not os.path.exists(index_path):
                logging.warning("Skip item %s: index.json not found", item_name)

                continue

            with open(index_path, "r", encoding="utf-8") as f:
                original_index_data = json.load(f)

            index_data = copy.deepcopy(original_index_data)
            # Remove digest field if present (should not be in deployed index)
            if "digest" in index_data:
                del index_data["digest"]

            # Process each manifest in the index
            for manifest_entry in index_data.get("manifests", []):
                manifest_path = os.path.join(item_dir, manifest_entry.get("path", ""))

                if not os.path.exists(manifest_path):
                    logging.warning("Skip manifest: %s not found", manifest_path)

                    continue

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)

                logging.info("Process manifest: %s", manifest_entry.get("path"))

                # Collect diff_ids for image config
                diff_ids = []

                # Process layers (rootfs) first to collect diff_ids
                for layer in manifest_data.get("layers", []):
                    layer_path = os.path.join(item_dir, layer.get("path", ""))

                    if os.path.exists(layer_path):
                        if os.path.isdir(layer_path):
                            # Compress directory to tar.gz
                            blob_hash, uncompressed_hash, blob_size = await self._deploy_layer_blob(
                                layer_path, sha256_dir
                            )

                            logging.info("Create layer blob: %s (uncompressed: %s)", blob_hash, uncompressed_hash)

                            # Store uncompressed hash for diff_ids
                            diff_ids.append(f"sha256:{uncompressed_hash}")

                            # Update layer with digest and size
                            layer["digest"] = f"sha256:{blob_hash}"
                            layer["size"] = blob_size
                            del layer["path"]

                        else:
                            # Single file layer
                            blob_hash, blob_size = await self._deploy_blob(layer_path, sha256_dir)

                            logging.info("Create layer blob: %s", blob_hash)

                            # Update layer with digest and size
                            layer["digest"] = f"sha256:{blob_hash}"
                            layer["size"] = blob_size
                            del layer["path"]

                        blobs_created += 1

                # Process config (image.json)
                if "config" in manifest_data:
                    config_entry = manifest_data["config"]
                    config_path = os.path.join(item_dir, config_entry.get("path", ""))

                    if os.path.exists(config_path):
                        blob_hash, blob_size = await self._deploy_image_config(config_path, sha256_dir, diff_ids)

                        logging.info("Create config blob: %s", blob_hash)

                        # Update manifest with digest and size
                        manifest_data["config"]["digest"] = f"sha256:{blob_hash}"
                        manifest_data["config"]["size"] = blob_size
                        del manifest_data["config"]["path"]

                        blobs_created += 1

                # Process aosService (service.json)
                if "aosService" in manifest_data:
                    service_entry = manifest_data["aosService"]
                    service_path = os.path.join(item_dir, service_entry.get("path", ""))

                    if os.path.exists(service_path):
                        blob_hash, blob_size = await self._deploy_blob(service_path, sha256_dir)

                        logging.info("Create aosService blob: %s", blob_hash)

                        # Update manifest with digest and size
                        manifest_data["aosService"]["digest"] = f"sha256:{blob_hash}"
                        manifest_data["aosService"]["size"] = blob_size
                        del manifest_data["aosService"]["path"]

                        blobs_created += 1

                # Deploy modified manifest
                manifest_blob_hash, manifest_blob_size = await self._deploy_spec(manifest_data, sha256_dir)

                logging.info("Deploy manifest blob: %s", manifest_blob_hash)

                # Update index entry with manifest digest and size
                manifest_entry["digest"] = f"sha256:{manifest_blob_hash}"
                manifest_entry["size"] = manifest_blob_size
                del manifest_entry["path"]

                blobs_created += 1

            # Deploy modified index (without digest field)
            index_blob_hash, _ = await self._deploy_spec(index_data, sha256_dir)

            logging.info("Deploy index blob: %s", index_blob_hash)

            blobs_created += 1

            # Add digest field to original index.json file
            original_index_data["digest"] = f"sha256:{index_blob_hash}"

            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(original_index_data, f, indent=4)

            logging.info("Update index.json with digest field")

            items_processed += 1

            print("\nUpdate complete:")
            print(f"  Items processed: {items_processed}")
            print(f"  Blobs created: {blobs_created}")

            logging.info("Update complete: %d items, %d blobs", items_processed, blobs_created)

    async def _deploy_blob(self, file_path: str, dst_dir: str) -> tuple[str, int]:
        """
        Create a blob from a file.

        Args:
            file_path: Path to source file
            sha256_dir: Directory to store blobs
            is_json: Whether the file is JSON (for pretty formatting)

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        with open(file_path, "rb") as f:
            content = f.read()

        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        blob_size = len(content)

        # Write blob
        blob_path = os.path.join(dst_dir, sha256_hash)

        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size

    async def _deploy_image_config(self, file_path: str, dst_dir: str, diff_ids: List[str]) -> tuple[str, int]:
        """
        Create a blob from image config file with diff_ids added.

        Args:
            file_path: Path to source config file
            dst_dir: Directory to store blobs
            diff_ids: List of uncompressed layer digests

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        # Read the original config file
        with open(file_path, "r", encoding="utf-8") as f:
            config_content = json.load(f)

        # Update rootfs with diff_ids if provided
        if diff_ids:
            if "rootfs" not in config_content:
                config_content["rootfs"] = {}

            config_content["rootfs"]["diff_ids"] = diff_ids
            config_content["rootfs"]["type"] = "layers"

        # Deploy the config as a spec
        return await self._deploy_spec(config_content, dst_dir)

    async def _deploy_layer_blob(self, dir_path: str, dst_dir: str) -> tuple[str, str, int]:
        """
        Create a compressed tar.gz blob from a directory.

        Args:
            dir_path: Path to source directory
            dst_dir: Directory to store blobs

        Returns:
            Tuple of (SHA256 hash, uncompressed hash, blob size in bytes)
        """
        # Create temporary tar.gz file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_uncompressed:
            tmp_uncompressed_path = tmp_uncompressed.name

        try:
            # Create uncompressed tar archive first
            with tarfile.open(tmp_uncompressed_path, "w") as tar:
                tar.add(dir_path, arcname=os.path.basename(dir_path))

            # Read uncompressed content and calculate hash
            with open(tmp_uncompressed_path, "rb") as f:
                uncompressed_content = f.read()

            uncompressed_hash = hashlib.sha256(uncompressed_content).hexdigest()

            # Create tar.gz archive
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(dir_path, arcname=os.path.basename(dir_path))

            # Read compressed content
            with open(tmp_path, "rb") as f:
                content = f.read()

            # Calculate SHA256
            sha256_hash = hashlib.sha256(content).hexdigest()
            blob_size = len(content)

            # Write blob
            blob_path = os.path.join(dst_dir, sha256_hash)

            with open(blob_path, "wb") as f:
                f.write(content)

            return sha256_hash, uncompressed_hash, blob_size

        finally:
            # Clean up temporary files
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

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
        # Serialize manifest to JSON
        spec_json = json.dumps(spec_data, indent=4)
        content = spec_json.encode("utf-8")

        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        blob_size = len(content)

        # Write blob
        blob_path = os.path.join(dst_dir, sha256_hash)

        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size
