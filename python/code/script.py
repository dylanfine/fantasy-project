import requests
import json
import pandas as pd
import re
import boto3
from botocore.exceptions import ClientError
from pretty_html_table import build_table

ENDPOINT_URL = 'https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl-season-player-props/season-player-specials?marketFilterId=rank&preMatchOnly=true&eventsLimit=5000&lang=en'

#Faking the headers so bovada thinks its a real web traffic request
headers_string = '''
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
''' 

def headers_to_json(headers_string):
    headers = {}
    lines = headers_string.strip().split("\n")
    for i in range(0, len(lines), 2):
        key = lines[i].strip()[:-1]
        value = lines[i+1].strip()
        headers[key] = value
    return headers

def extract_decimal(s: str) -> float:
    match = re.search(r"(\d+\.\d+)", s)
    if match:
        return float(match.group(1))
    return None


def extract_player_stat(line: str) -> tuple:
    
    # Regular expression to match lines that contain player names and stats
    pattern = r'^(?P<name>[A-Za-z. ]+) (?P<year>\d{4}-\d{2}) Regular Season Total (?P<stat>.+)$'

    match = re.match(pattern, line)
    if match:
        return match.group('name'), match.group('stat')
    return None

def send_email(html):
    SENDER = "Financial Analysis <dylanjfine@gmail.com>"
    RECIPIENT = "dylanjfine@gmail.com"
    AWS_REGION = "us-east-2"
    SUBJECT = "Your Daily Financial Summary"
    # Text value only shows up if HTML fails - otherwise text needs to be put in the HTML
    BODY_TEXT = "Your email client cannot support HTML"
    BODY_HTML = html
    CHARSET = "UTF-8"
    client = boto3.client("ses", region_name=AWS_REGION)
    try:
        # Provide the contents of the email.
        response = client.send_email(
            ConfigurationSetName="email_open",
            Destination={
                "ToAddresses": [
                    RECIPIENT,
                ],
            },
            Message={
                "Body": {
                    "Html": {
                        "Charset": CHARSET,
                        "Data": BODY_HTML,
                    },
                    "Text": {
                        "Charset": CHARSET,
                        "Data": BODY_TEXT,
                    },
                },
                "Subject": {
                    "Charset": CHARSET,
                    "Data": SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response["Error"]["Message"])
    else:
        print("Email sent! Message ID:"),
        print(response["MessageId"])

def lambda_handler(event,context):
    data = requests.get(ENDPOINT_URL).json()

    lst = []
    for event in data[0]['events']:
        markets = event ['displayGroups'][0]['markets']
        for market in markets:
            market_description = market['description']
            outcomes = market['outcomes']
            
            if "Sacks" in market_description or "Tackles" in market_description:
                continue
            elif '2023-24 To' in market_description:
                d = {}
                d['stat'] = market_description.replace('2023-24 To','').strip()
                for outcome in outcomes:
                    d['player_name'] = outcome['description']
                    d['odds'] = outcome['price']['american']
                    lst.append(d.copy())
            else:   
                d = {}
                play_stat_tup = extract_player_stat(market_description)
                if not play_stat_tup:
                    continue
                name,stat = play_stat_tup
                d['player_name'] = name
                d['stat'] = stat
                for outcome in outcomes:
                    outcome_description = outcome['description']
                    if 'Over' in outcome_description:
                        d['line'] = extract_decimal(outcome_description)
                        d['odds'] = outcome['price']['american']
                lst.append(d)

    df = pd.DataFrame(lst)

    html = (
        f"""<body><h1>See fantasy data below!!</h1></body>"""
        + build_table(df, color="green_light")
    )
    send_email(html)
