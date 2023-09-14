import requests
import json
import pandas as pd
import re
import boto3
from botocore.exceptions import ClientError
from pretty_html_table import build_table
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from io import StringIO

ENDPOINT_URL = "https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl-season-player-props/season-player-specials?marketFilterId=rank&preMatchOnly=true&eventsLimit=5000&lang=en"

# Faking the headers so bovada thinks its a real web traffic request
headers_string = """
Accept:
application/json, text/plain, */*
Accept-Encoding:
gzip, deflate, br
Accept-Language:
en-US,en;q=0.9
Referer:
https://www.bovada.lv/
Sec-Ch-Ua:
"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"
Sec-Ch-Ua-Mobile:
?0
Sec-Ch-Ua-Platform:
"macOS"
Sec-Fetch-Dest:
empty
Sec-Fetch-Mode:
cors
Sec-Fetch-Site:
same-origin
User-Agent:
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36
X-Channel:
desktop
X-Sport-Context:
FOOT
"""


def headers_to_json(headers_string):
    headers = {}
    lines = headers_string.strip().split("\n")
    for i in range(0, len(lines), 2):
        key = lines[i].strip()[:-1]
        value = lines[i + 1].strip()
        headers[key] = value
    return headers


def send_dataframe_as_attachment(html, df, filename="data.csv"):
    SUBJECT = "Your Daily Fantasy Magic"
    SENDER = "Fantasy Greatness <dylanjfine@gmail.com>"
    RECEIPEINTS = ["dylanjfine@gmail.com", "andrewboppart@gmail.com"]

    # Convert DataFrame to CSV string
    csv_buffer = StringIO()
    df.to_csv(csv_buffer)

    # Create a new SES client
    client = boto3.client("ses")

    # Create a multipart/mixed parent container
    msg = MIMEMultipart("mixed")
    msg["Subject"] = SUBJECT

    # Add the HTML message part
    text_part = MIMEText(html, "html")
    msg.attach(text_part)

    # Add the CSV attachment
    att = MIMEBase("application", "octet-stream")
    att.set_payload(csv_buffer.getvalue())
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    # Send the email
    response = client.send_raw_email(
        Source=SENDER, Destinations=RECEIPEINTS, RawMessage={"Data": msg.as_string()}
    )

    return response


def lambda_handler(event, context):
    headers = headers_to_json(headers_string)

    url = "https://bv2.digitalsportstech.com/api/game?sb=bovada&league=142"
    r = requests.get(url)
    game_ids = [
        provider["id"]
        for item in r.json()
        for provider in item["providers"]
        if provider["name"] == "nix"
    ]
    lst = []
    for game_id in game_ids:
        market_url = f"https://bv2.digitalsportstech.com/api/grouped-markets/v2/categories?sb=bovada&gameId={game_id}&sgmOdds=true"
        res = requests.get(market_url).json()
        over_unders = res["ou"]
        for ou_cat in over_unders:
            stat_url = f"https://bv2.digitalsportstech.com/api/dfm/marketsByOu?sb=bovada&gameId={game_id}&statistic={urllib.parse.quote(ou_cat)}"
            res = requests.get(stat_url).json()
            lst.append(res)

    df_lst = []
    for cat in lst:
        for player in cat[0]["players"]:
            d = {}
            d["player"] = player["name"]
            d["team"] = player["team"]
            d["stat"] = cat[0]["statistic"]
            for market in player["markets"]:
                if market["condition"] == 1:
                    d["under_line"] = market["value"]
                    d["under_odds"] = market["odds"]
                elif market["condition"] == 3:
                    d["over_line"] = market["value"]
                    d["over_odds"] = market["odds"]
            df_lst.append(d)

    df = pd.DataFrame(df_lst)

    html = f"""<body><h1>See fantasy data below!!</h1></body>""" + build_table(
        df, color="green_light"
    )
    send_dataframe_as_attachment(html, df)
