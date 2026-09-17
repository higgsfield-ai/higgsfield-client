"""Agent API example: one session, one autonomous turn, a follow-up.

Requires an API key with Agent API access (contact support@higgsfield.ai).
"""

from higgsfield_client import SyncClient

# Reads HF_KEY or HF_API_KEY + HF_API_SECRET from the environment.
client = SyncClient()

# Sessions are durable: keep the id, the agent remembers previous turns.
session = client.agents.sessions.create()
print(session)

# run() sends the task and polls until the turn ends (backoff 2s -> 10s).
result = client.agents.sessions.run(
    session.session_id,
    "Generate one image of a quiet alpine lake at sunrise, editorial "
    "photography, 4:3. Reply with the image URL.",
    # If the agent asks a clarifying question, answer it here; without the
    # handler run() returns TurnResult(status="awaiting_input") instead.
    on_question=lambda question: "Photorealistic style.",
)
print(result.status)  # completed | failed | awaiting_input
print(result.text)  # the agent's answer
print(result.asset_urls)  # URLs of generated assets

# Follow-ups reuse the same session (memory persists).
follow_up = client.agents.sessions.run(
    session.session_id,
    "Now make a 16:9 version of the same scene at dusk.",
)
print(follow_up.text)

# Give the agent an input file: upload, then reference the URL in the task.
with open("image.jpeg", "rb") as f:
    url = client.agents.media.upload(f.read(), extension="jpeg", type="image")
result = client.agents.sessions.run(
    session.session_id, f"Animate this image into a 5s clip: {url}"
)
print(result.asset_urls)
