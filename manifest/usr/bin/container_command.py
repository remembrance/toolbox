#!/usr/bin/env python3

from os import getenv
from sys import exit

from kubernetes import client, config, stream

try:
    config.load_incluster_config()
except config.ConfigException as e:
    print(e)
    exit(10)

try:
    k8s = client.CoreV1Api()
except client.ApiException as e:
    print(e)
    exit(11)

selector = getenv("POD_SELECTOR", None)
namespace = getenv("K8S_NAMESPACE", None)
container = getenv("CONTAINER_NAME", None)
command = getenv("CONTAINER_COMMAND", None)

if None in [selector, namespace, container, command]:
    raise ValueError("environment variables missing")

try:
    resp = k8s.list_namespaced_pod(namespace=namespace, label_selector=selector)

    pods = [x.spec.hostname for x in resp.items if x.spec.hostname]
    for name in pods:
        resp = k8s.read_namespaced_pod(name=name, namespace=namespace)

        exec_command = [
            "/bin/sh",
            "-c",
            command,
        ]

        resp = stream.stream(
            k8s.connect_get_namespaced_pod_exec,
            name,
            namespace,
            container=container,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )

        print(
            "====== Cleanup %s: =======\n%s\n" % (name, resp if resp else "<no output>")
        )

except client.ApiException as e:
    print(e)
    exit(12)
