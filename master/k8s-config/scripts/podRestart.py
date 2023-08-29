import os
import logging
from flask import Flask, request, jsonify, Response
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slackeventsapi import SlackEventAdapter
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO)

#set global vars
pod_name = None
Namespace = None
workerPod = None
botUser = None

# Load in-cluster configuration for Kubernetes Python client.
config.load_incluster_config()
v1 = client.CoreV1Api()

# Intiate flask app
app = Flask(__name__)

# Replace 'SLACK_API_TOKEN' and other variables with your actual values from your Slack app settings.
slack_bot_token = os.environ["SLACK_API_TOKEN"].strip()
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"].strip()
bot_mention = f"<@{os.environ['SLACK_BOT_ID'].strip()}>"
bot_channel = os.environ["SLACK_CHANNEL_ID"].strip()

# Create a Slack client
slack_client = WebClient(token=slack_bot_token)

# Create a SignatureVerifier to check the request signatures (required for events)
signature_verifier = SignatureVerifier(slack_signing_secret)

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
        text = "Challenge processed successfully"
        return f"{text}", 200

    # Verify the request signature using the raw data and headers
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return f"error - Invalid request: signature invalid", 403

    data = request.get_json()

    # Check if the request contains an event
    if "event" in data and "type" in data["event"]:
    # Handle mentions
        if data["event"]["type"] == "app_mention":
            # Extract the text of the message that mentioned the bot
            message = data["event"]["attachments"][0]["text"]
            
            # Grabbing origin channel
            origin_channel = data["event"]["channel"]
            
            # Check if the bot is mentioned in the message
            if bot_mention in message:
                # Extract the fields from the attachments
                attachments = data["event"]["attachments"]
                pod_name = None
                Namespace = None
                
                for attachment in attachments:
                    if "fields" in attachment:
                        for field in attachment["fields"]:
                            if field["title"] == "pod":
                                pod_name = field["value"].strip()
                            elif field["title"] == "namespace":
                                Namespace = field["value"].strip()
                            elif field["title"] == "cluster":
                                cluster = field["value"].strip()
                        print("Pod Name:", pod_name)
                        print("Namespace:", Namespace)
                # Check if both pod_name and namespace are found
                if pod_name and Namespace:
                    def slack_messaging_post():
                        # To reduce clutter in the main channel, redirect messages are going directly to the worker bot's direct channel(eventually)
                        slack_client.chat_postMessage(channel=origin_channel, text=f'{botUser} {pod_name} {Namespace}')
                        response = f'The restart of {pod_name} in the namespace {Namespace} has been forwarded to the worker {workerPod}!'
                        slack_client.chat_postMessage(channel=origin_channel, text=response)
                        logging.info(response)
                    try:
                        if cluster=='<WORKER_CLUSTERNAME_0>':
                            workerPod = "podrecycler-<cluster>"
                            botUser = "<@cluster_bot_id>"                            
                            slack_messaging_post()
                        elif cluster=='<WORKER_CLUSTERNAME_1>':
                            workerPod = "podrecycler-<cluster>"
                            botUser = "<@cluster_bot_id>" 
                            slack_messaging_post()                        
                    except Exception as e:
                        response = f"A valid cluster was not provided exception: {str(e)}"
                        logging.info("cluster is: %s", cluster)
                        logging.error(response)
                        # Send the response message back to the channel (Optional)
                        #slack_client.chat_postMessage(channel=bot_channel, text=response)
    return jsonify({"message": "Request received"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)