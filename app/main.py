from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# ... (all previous imports and code from the previously provided full main.py remain exactly the same)

# Add this at the bottom, before the root endpoint
active_connections: list[WebSocket] = []

@app.websocket("/ws/approvals")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# The rest of the file (routers, middleware, root endpoint) is unchanged from the previous full main.py provided.