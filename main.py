from fastapi import FastAPI
import random, string
app = FastAPI()
KEYS={}
def make_key():
 return f"RT-{''.join(random.choices(string.ascii_uppercase+string.digits, k=8))}-{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}"
@app.get("/")
def home():
 return {"status":"RoboTrader SA Running"}
@app.get("/generate-key")
def gen():
 k=make_key()
 KEYS[k]={"valid":True}
 return {"key":k}
@app.get("/verify/{key}")
def verify(key: str):
 return {"valid": key in KEYS}
