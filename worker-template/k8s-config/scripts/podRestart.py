import os
import logging
from flask import Flask, request, jsonify, Response
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slackeventsapi import SlackEventAdapter
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO)

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
        logging.info("%s", text)
        return f"{text}", 200

    # Verify the request signature using the raw data and headers
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        logging.info("Error - Invalid request: signature invalid")
        return f"error - Invalid request: signature invalid", 403

    # Check if the request contains an event
    if "event" in data and "type" in data["event"]:
    # Handle mentions
        if data["event"]["type"] == "app_mention":
            message = data["event"]
            
            # Grabbing origin channel
            origin_channel = data["event"]["channel"]
            # Determine which user mentioned the app
            taggingUserId = data["event"]["user"]
            slackIdLookup = slack_client.users_info(user=taggingUserId)
            userInfo = slackIdLookup["user"]
            requestingUserDN = userInfo["profile"]["display_name"] or userInfo["profile"]["real_name"]
            logging.info(requestingUserDN)
            text = message.get("text", "").strip()

            if text.startswith(bot_mention):
                words = text.split()
                if len(words) >= 2:
                    pod_name = words[1]
                    namespace = words[2]
                    try:
                    # Restart the pod by deleting and re-creating it
                        v1.delete_namespaced_pod(pod_name, namespace)
                        message=f'Restarting pod {pod_name} in namespace {namespace} at the request of {requestingUserDN}.'
                        slack_client.chat_postMessage(channel=origin_channel, text=message)
                        logging.info("%s", message)
                        return f"{message}", 200
                    except Exception as e:
                        message="An error occurred while restarting the pod:"
                        logging.info("%s %s", message, {str(e)})
                        slack_client.chat_postMessage(channel=origin_channel, text=f"{message} {str(e)}")
                        return f"{message}", 403
    return jsonify({"message": "Request received"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)