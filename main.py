from asyncio import Queue
from fastapi import FastAPI, WebSocket
from concurrent.futures import ThreadPoolExecutor
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.agents import load_tools, initialize_agent
from langchain.agents import AgentType

# i used thread, asyncio for run funcs asyncronous
import threading
import asyncio

import time
import os

os.environ["OPENAI_API_KEY"] = "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"

app = FastAPI()
request_queue = Queue() # this queue manages client's inputs

llm = ChatOpenAI(temperature=0.0)
math_llm = OpenAI(temperature=0.0)

cur_socket: WebSocket = None # this is current connected socket
cur_state = 0 # this state means ; 0: no connection -> acceptable, 1: one client connected, 2: processing now
lock = threading.Lock()

# this thread is for, getting input from input request_queue
class CustomThread(threading.Thread):
    def run(self):
        start_time = time.time()
        while time.time() - start_time <= 60.0: # wait for 60 seconds -- for client's input
            #print(time.time()) # debugging
            if (request_queue.qsize() == 0): # no input queued
                time.sleep(2) # wait for 2 seconds --> means check again after 2 seconds
            else:
                self.value = asyncio.run(request_queue.get()) # there's an input
                print('queue get', self.value) # this is for debugging
                break
        else:
            self.value = '' # time out --> user doesn't input anything
            print('timeout') # for debugging

#redefine get_input
def get_input() -> str:
    print("get_input")
    thread = CustomThread()
    thread.start()
    thread.join()
    return thread.value

#redefine get_output
def get_output(actionInput: str) -> None:
    global cur_socket
    print('get_output:', actionInput)
    print('cur_socket', cur_socket)
    if cur_socket == None:
        return

    def send_func(resp: str):
        asyncio.run(cur_socket.send_text(resp))
    print('sending output')
    # asyncio.run(cur_socket.send_text(actionInput))
    thread_send = threading.Thread(target=send_func, args=(actionInput,))
    thread_send.start()
    thread_send.join()

tools = load_tools(["ddg-search", "human"], llm=math_llm, 
                   input_func=get_input,
                   prompt_func=lambda actionInput: get_output(actionInput))
agent_chain = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
)

# this is thread - that runs agent_chain.run() -> it's independent from websocket_endpoint
def thread_func(websocket: WebSocket, req: str):
    async def real_func(websocket: WebSocket, req: str):
        global cur_state
        try:
            response = agent_chain.run(req)
            lock.acquire()
            await websocket.send_text("Final Result: " + response)
            cur_state = 1
            lock.release()
        except Exception as e:
            print(f"An error occurred: {str(e)}")
    asyncio.run(real_func(websocket, req))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global cur_state
    global cur_socket
    if cur_state:
        websocket.close(reason="Already processing, try again later.")
        return
    # because cur_state and cur_socket is using in threads, must use mutex
    lock.acquire()
    cur_state = 1
    cur_socket = websocket
    lock.release()
    await websocket.accept()
    try:
        while True:
            req = await websocket.receive_text()
            lock.acquire() # before accessing cur_state and cur_socket
            if cur_state == 2: # now processing --> this is input for get_input func
                print('queue put', req) # debugging
                await request_queue.put(req)
            else:
                # run in thread
                cur_state = 2 # set state to processing
                thread = threading.Thread(target=thread_func, args=(websocket, req)) # make thread and run
                thread.start()            
                await websocket.send_text("Processing, wait while there's a question or final result.") # show user that server is processing his request
            lock.release()
    except Exception as e:
        cur_state = 0 # this means, now the websocket is disconnected, and server is ready for new connection (new socket)
        print(f"WebSocket connection closed: {e}")
