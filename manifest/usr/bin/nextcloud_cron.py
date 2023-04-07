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

label_name = getenv("LABEL_APP_NAME", None)
label_component = getenv("LABEL_APP_COMPONENT", None)
namespace = getenv("K8S_NAMESPACE", None)
container = getenv("CONTAINER_NAME", None)

if None in [label_name, label_component, namespace, container]:
    raise ValueError("environment variables missing")

selector = ",".join(
    [
        f"app.kubernetes.io/name={label_name}",
        f"app.kubernetes.io/component={label_component}",
    ]
)

try:
    resp = k8s.list_namespaced_pod(namespace=namespace, label_selector=selector)

    pods = [x.spec.hostname for x in resp.items if x.spec.hostname]
    for name in pods:
        resp = k8s.read_namespaced_pod(name=name, namespace=namespace)

        # https://docs.nextcloud.com/server/latest/admin_manual/configuration_server/background_jobs_configuration.html#cron
        exec_command = [
            "/bin/sh",
            "-c",
            'su -p www-data -s /bin/sh -c "php -f /var/www/html/cron.php"',
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
