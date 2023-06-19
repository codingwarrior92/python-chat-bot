To use go to launch websocket from terminal via uvicorn main:app --reload --ws websockets

then go to websocket testing site https://websocketking.com/

enter the following as connection address and click connect 

ws://localhost:8000/ws

it should say successful and you should be able to interact with agent
through socket. As stated it we are aiming to pass inputs (to agent and to tool) through a websocket or endpoint.


To get an idea of how agents work see the how to use agents and tools notebooks.
