ARG ALPINE_VERSION=3.17
FROM alpine:$ALPINE_VERSION

# base packages
RUN apk -U add \
  bind-tools \
  mariadb-client \
  python3 \
  python3-dev \
  py3-pip \
  coreutils \
  nmap \
  tcpdump \
  ngrep \
  mtr \
  vim

# script dependencies
RUN pip install boto3

COPY manifest /
