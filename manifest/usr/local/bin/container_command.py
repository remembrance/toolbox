#!/usr/bin/env python3

from os import getenv

from kubectlme import ContainerCommand

selector = getenv("POD_SELECTOR")
namespace = getenv("K8S_NAMESPACE")
container = getenv("CONTAINER_NAME")
command = getenv("CONTAINER_COMMAND")

_ = ContainerCommand(selector, namespace, container, command).run()
