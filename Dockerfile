FROM python:3.9

# Install necessary dependencies
RUN apt-get update \
    && apt-get install -y apt-transport-https curl pip \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl \
    && pip install flask \
    && pip install kubernetes \
    && pip install slack_sdk \
    && pip install slackeventsapi

# Make scripts directory
RUN mkdir /scripts

# Set the working directory
WORKDIR /scripts