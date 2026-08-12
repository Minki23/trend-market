import paho.mqtt.subscribe as subscribe
import yfinance as yf

def on_message_print(client, userdata, message):
    print(yf.Ticker(message.payload.decode("utf-8")).history(period='1mo'))

subscribe.callback(
    on_message_print,
    "data",
    hostname="localhost",
    port=1883,
    userdata={"message_count": 0}

)