"""Messages storage and display for WebSocket communication."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


def _get_id(entity: Dict[str, Any]) -> str:
    """
    Get ID or codename of an entity.

    Args:
        entity: Entity dictionary

    Returns:
        ID or codename of the entity
    """
    return entity.get("id", entity.get("codename", "unknown"))


class Messages:
    """Store and display sent and received WebSocket messages."""

    def __init__(self):
        """Initialize messages storage."""
        self._messages: Dict[str, Dict[str, Any]] = {}

    def notify_sent(self, system_id: str, txn: str, message: Dict[str, Any]) -> None:
        """
        Store sent message.

        Args:
            system_id: System ID from header
            txn: Transaction ID from header
            message: Message data (without header)
        """
        self._add_message("TX", system_id, txn, message)

    def notify_received(self, system_id: str, txn: str, message: Dict[str, Any]) -> None:
        """
        Store received message.

        Args:
            message: Message data (without header)
            system_id: System ID from header
            txn: Transaction ID from header
        """
        self._add_message("RX", system_id, txn, message)

    def show_message(self, message_type: str) -> None:
        """
        Display stored message of given type.
        Args:
            message_type: Type of message to display
        """
        if message_type not in self._messages:
            raise ValueError(f"No message of type '{message_type}' stored.")

        message_record = self._messages[message_type]

        self._display_header(message_type, message_record)
        self._display_message(message_type, message_record)

    def clear(self) -> None:
        """Clear all stored messages."""
        logging.info("Clear all stored messages")

        self._messages.clear()

    def _add_message(self, direction: str, system_id: str, txn: str, message: Dict[str, Any]) -> None:
        """
        Store and display sent message.

        Args:
            system_id: System ID from header
            txn: Transaction ID from header
            message: Message data (without header)
        """
        message_type = message.get("messageType", "unknown")
        timestamp = datetime.now()

        message_record = {
            "timestamp": timestamp,
            "system_id": system_id,
            "txn": txn,
            "data": message,
            "direction": direction,
        }

        self._messages.update({message_type: message_record})
        self.show_message(message_type)

    def _display_header(self, message_type: str, message_record: Dict[str, Any]) -> None:
        """
        Display message header information.
        """
        print("====================================================================================================")
        print(
            f"{message_record['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}",
            f"{message_record['direction']} {message_type}",
        )
        print("----------------------------------------------------------------------------------------------------")

    def _display_message(self, message_type: str, message_record: Dict[str, Any]) -> None:
        """
        Display message in human-readable format.
        """

        if message_type == "unitStatus":
            self._display_unit_status(message_record)
        elif message_type == "monitoringData":
            self._display_monitoring_data(message_record)
        elif message_type == "alerts":
            self._display_alerts(message_record)
        else:
            print(json.dumps(message_record["data"], indent=4, ensure_ascii=False))

        print("====================================================================================================")

    def _display_unit_status(self, message_record: Dict[str, Any]) -> None:
        """
        Display unitStatus message in human-readable format.
        """
        print(f"IsDeltaInfo: {message_record['data']['isDeltaInfo']}")

        unit_config = message_record["data"].get("unitConfig")

        if unit_config is not None:
            print("Unit config:")

            for item in unit_config:
                print(f"\tversion: {item['version']}, state: {item['state']}")

        nodes = message_record["data"].get("nodes")

        if nodes is not None:
            print("Nodes:")

            for node in nodes:
                print(
                    f"\tid: {_get_id(node['identity'])}, title: {node['identity']['title']},",
                    f"type: {_get_id(node['nodeGroupSubject'])},",
                )
                print(
                    f"\tmaxDmips: {node['maxDmips']}, totalRam: {node['totalRam']},",
                    f"os: {node['osInfo']['os']}, arch: {node['cpus'][0]['archInfo']['architecture']}",
                )
                print(f"\tstate: {node['state']}, connected: {node['isConnected']}")

        items = message_record["data"].get("items")

        if items is not None:
            print("Items:")

            for item in items:
                print(f"\tid: {_get_id(item['item'])}, version: {item['version']}, state: {item['state']}")

        instances = message_record["data"].get("instances")

        if instances is not None:
            print("Instances:")

            for item in instances:
                item_id = _get_id(item["item"])
                subject_id = _get_id(item["subject"])

                print(
                    f"\titem: {item_id if item_id else item['item'].get('codename')},",
                    f"subject: {subject_id if subject_id else item['subject'].get('codename')},",
                    f"version: {item['version']}",
                )

                for instance in item["instances"]:
                    error_info = instance.get("errorInfo")

                    print(
                        f"\t\tinstance: {instance['instance']},",
                        f"state: {instance['state']},",
                    )

                    if error_info is not None:
                        print(f"\t\terror: {error_info['message']}")

                    print(f"\t\tnode: {instance['node']['codename']}, runtime: {instance['runtime']['codename']}")

    def _display_monitoring_data(self, message_record: Dict[str, Any]) -> None:
        """
        Display monitoringData message in human-readable format.
        """
        nodes = message_record["data"].get("nodes")

        if nodes is not None:
            for node in nodes:
                print(f"nodeID: {_get_id(node['node'])}")

                node_states = node.get("nodeStates")
                if node_states is not None:
                    for state in node_states:
                        print(
                            f"\ttimestamp: {state['timestamp']},",
                            f"state: {state['state']}, isConnected: {state['isConnected']}",
                        )

                for item in node["items"]:
                    print(
                        f"\ttimestamp: {item['timestamp']}, cpu: {item['cpu']}, ram: {item['ram']},",
                        f"download: {item['download']}, upload: {item['upload']}",
                    )

                    partitions = item.get("partitions", [])

                    if len(partitions) > 0:
                        print("\t", end="")

                    for i, partition in enumerate(partitions):
                        print(
                            f"{partition['name']}: {partition['usedSize']}",
                            end=", " if i < len(partitions) - 1 else "\n",
                        )

        instances = message_record["data"].get("instances")

        if instances is not None:
            for instance in instances:
                print(
                    f"itemID: {_get_id(instance['item'])}, subjectID: {_get_id(instance['subject'])},",
                    f"instance: {instance['instance']},",
                )
                print(f"\tnodeID: {_get_id(instance['node'])}")

                item_states = instance.get("itemStates")
                if item_states is not None:
                    for state in item_states:
                        print(f"\ttimestamp: {state['timestamp']}, state: {state['state']}")

                for item in instance["items"]:
                    print(
                        f"\ttimestamp: {item['timestamp']}, cpu: {item['cpu']}, ram: {item['ram']},",
                        f"download: {item['download']}, upload: {item['upload']}",
                    )

                    partitions = item.get("partitions", [])

                    if len(partitions) > 0:
                        print("\t", end="")

                    for i, partition in enumerate(partitions):
                        print(
                            f"{partition['name']}: {partition['usedSize']}",
                            end=", " if i < len(partitions) - 1 else "\n",
                        )

    def _display_alerts(self, message_record: Dict[str, Any]) -> None:
        """
        Display alerts message in human-readable format.
        """
        items = message_record["data"].get("items", [])

        for alert in items:
            tag = alert.get("tag")

            print(f"\ttimestamp: {alert['timestamp']}, tag: {tag},")

            if tag == "downloadProgressAlert":
                print(f"\tdigest: {alert['digest']},")
                print(f"\turl: {alert['url']},")
                print(
                    f"\tstate: {alert['state']},",
                    f"downloaded: {alert['downloadedBytes']}, total: {alert['totalBytes']}",
                )
            elif tag == "updateItemInstanceAlert":
                print(
                    f"\titem: {_get_id(alert['item'])}, subject: {_get_id(alert['subject'])},",
                    f"instance: {alert['instance']}, version: {alert['version']},",
                )
                print(f"\tmessage: {alert['message']}")
            else:
                print(json.dumps(alert, indent=4, ensure_ascii=False))
