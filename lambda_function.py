# -*- coding: utf-8 -*-
from __future__ import print_function

import boto3
from decimal import Decimal
import urllib
import requests
import json
import os
import logging

print('Loading function')

# ref https://devdocs.line.me/ja/#reply-message
REQUEST_URL = 'https://api.line.me/v2/bot/message/reply'
DOCOMO_ZATUDANAI = 'https://api.apigw.smt.docomo.ne.jp/dialogue/v1/dialogue?APIKEY=' + os.environ['DOCOMO_APIKEY']

REQUEST_HEADERS = {
  'Authorization': 'Bearer ' + os.environ['ACCESS_TOKEN'],
  'Content-type': 'application/json'
}
DOCOMO_HEADERS = {
  'Content-type': 'application/json'
}


GET_CONTENT_URL = 'https://api.line.me/v2/bot/message/%s/content'

GET_CONTENT_HEADER = {
  'Authorization': 'Bearer ' + os.environ['ACCESS_TOKEN'],
}

rekognition = boto3.client('rekognition',region_name='us-west-2')


# --------------- Helper Functions to call Rekognition APIs ------------------


def detect_faces(bucket, key):
    response = rekognition.detect_faces(Image={"S3Object": {"Bucket": bucket, "Name": key}})
    return response


def detect_labels(bucket, key):
    response = rekognition.detect_labels(Image={"S3Object": {"Bucket": bucket, "Name": key}})

    # Sample code to write response to DynamoDB table 'MyTable' with 'PK' as Primary Key.
    # Note: role used for executing this Lambda function should have write access to the table.
    #table = boto3.resource('dynamodb').Table('MyTable')
    #labels = [{'Confidence': Decimal(str(label_prediction['Confidence'])), 'Name': label_prediction['Name']} for label_prediction in response['Labels']]
    #table.put_item(Item={'PK': key, 'Labels': labels})
    return response


def index_faces(bucket, key):
    # Note: Collection has to be created upfront. Use CreateCollection API to create a collecion.
    #rekognition.create_collection(CollectionId='BLUEPRINT_COLLECTION')
    response = rekognition.index_faces(Image={"S3Object": {"Bucket": bucket, "Name": key}}, CollectionId="BLUEPRINT_COLLECTION")
    return response




def getRekognitaion(bucket, key):
    '''Demonstrates S3 trigger that uses
    Rekognition APIs to detect faces, labels and index faces in S3 Object.
    '''
    #print("Received event: " + json.dumps(event, indent=2))


    # Get the object from the event
    # bucket = event['Records'][0]['s3']['bucket']['name']
    # key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    try:
        # Calls rekognition DetectFaces API to detect faces in S3 object
        # response = detect_faces(bucket, key)

        # Calls rekognition DetectLabels API to detect labels in S3 object
        response = detect_labels(bucket, key)

        # Calls rekognition IndexFaces API to detect faces in S3 object and index faces into specified collection
        #response = index_faces(bucket, key)

        # Print response to console.
        print(response)

        return response
    except Exception as e:
        print(e)
        print("Error processing object {} from bucket {}. ".format(key, bucket) +
              "Make sure your object and bucket exist and your bucket is in the same region as this function.")
        raise e
        
def getContent(id,output):
  """
  getContent refs https://devdocs.line.me/ja/#content
  Lambda では tmp ディレクトリが使えるので、tmpに保存します
  ただし、tmp 以下は 他プロジェクトと名前被り等ありえるので
  本番運用時は注意が必要
  """
  response = requests.get(GET_CONTENT_URL % id , headers=GET_CONTENT_HEADER)
  if response.status_code == 200:
    f = open(output, 'w')
    f.write(response.content)
    f.close()



def getDocomoAI(userID,utt):
  """
  refs https://dev.smt.docomo.ne.jp?p=docs.api.page&api_name=dialogue&p_name=api_1#tag01

  """
  request_body = {
      "utt":utt,
      "context":userID
  }
  response = requests.post(DOCOMO_ZATUDANAI, headers=DOCOMO_HEADERS, data=json.dumps(request_body))
  res_body = response.json()
  return res_body['utt']
    

def lambda_handler(event, context):
  """
  main function
  """
  print(event)
  print(context)
  
  # refs https://devdocs.line.me/ja/#webhooks
  body = json.loads(event['body'])
  for event in body['events']:
    # refs https://devdocs.line.me/ja/#reply-message
    reply_token = event['replyToken']
    message = event['message']
    
    request_body = {}
    
    # メッセージタイプ refs https://devdocs.line.me/ja/#webhook-event-object
    # field message
    if message['type'] == 'text':
      userId  = event['source']['userId']

      # text message request_body refs https://devdocs.line.me/ja/#reply-message
      request_body = {
        "replyToken": reply_token,
        "messages" : [{
            "type" : "text",
            "text" : getDocomoAI(userId,message['text'])
            }]
        }
    elif message['type'] == 'image':
      getContent(message['id'],'/tmp/'+message['id'])

      # S3へ一旦保存してから Rekognitaionに回します
      # この時 Rekognitaion は 東京リージョンでは動作しない（2017年2月現在)ので S3のリージョンをオレゴン等アメリカにしておきます
      s3_client = boto3.client('s3',region_name='us-west-2')
      s3_client.upload_file('/tmp/'+message['id'], os.environ['S3_BUCKET'], message['id'])

      # tmp以下消去
      os.remove('/tmp/'+message['id'])

      
      response = getRekognitaion(os.environ['S3_BUCKET'],message['id'])

      print(response)
      # Detecting Labels refs http://docs.aws.amazon.com/rekognition/latest/dg/howitworks-labeling.html#howitworks-detecting-labels
      labels_text = ""
      for label_str in response['Labels']:
          label = label_str
          print(type(label))
          print(label)
          labels_text = labels_text + label['Name'] + "    "

      # LINE へ返却
      request_body = {
        "replyToken": reply_token,
        "messages" : [{
            "type" : "text",
            "text" : labels_text
            }]
        }


    else:
      request_body = {
        "replyToken": reply_token,
        "messages" : [{
            "type" : "text",
            "text" : "Sorry..."
            }]
        }

    # 本番運用では 画像解析にかかる時間を短く見せるため
    # L      -> Webhook -> λ
    # I      <- reply      λ  
    # N                    λ --> 別λ
    # E     <---- push --------   別λ
    # というピタゴラスイッチにした方がレスポンスが早くなっているように見えてよい
    response = requests.post(REQUEST_URL, headers=REQUEST_HEADERS, data=json.dumps(request_body))
    print(response)

"""
# push message
refs <https://devdocs.line.me/ja/#push-message>

送信先識別子は <https://devdocs.line.me/ja/#webhooks>  の `"source"{"userId":XXXXXX}`

push できない時は、LINE MessangerAPIのプランがフリー以外（無料枠ならDevelop trial）になっているか確認

"""

