import logging
import boto3
import json
import random
from botocore.exceptions import ClientError
from datetime import datetime

def push_to_SNS(faceID, phone, passcode):
    # Get the service resource
    sqs = boto3.resource('sqs', 'us-east-1')

    # Get the queue
    queue = sqs.get_queue_by_name(QueueName='')

    # Create a new message
    message = json.dumps({
        "faceID":str(faceID),
        "phone": str(phone),
        "passcode":str(passcode)
    })
    print(message)
    queue.send_message(MessageBody=message)

def send_message(message, phone):
    client = boto3.client("sns")
    client.publish(MessageStructure='string', PhoneNumber=phone, Message=message)

def insert_visitor(faceID, name, phone_number, file, bucket):
    db = boto3.resource('dynamodb')
    table = db.Table('visitors')
    table = db.Table('visitors')
    response = table.put_item(
        Item={
            'faceID': faceID,
            'name': name,
            'phoneNumber': phone_number,
            'photos': [
                {
                    'objectKey': file,
                    'bucket': bucket,
                    'createdTimestamp': str(datetime.now())
                }
            ]
        }
    )
    return response

def insert_passcode(faceID, passcode):
    db = boto3.resource('dynamodb')
    table = db.Table('passcodes')
    curr = datetime.now().timestamp()
    response = table.put_item(
        Item={
            'faceID': faceID,
            'passcode': passcode,
            'createdTimestamp': int(curr),
            'validUntil': int(curr+300)
        }
    )
    return response

def create_passcode():
    passcode = str(random.randint(1000, 9999))
    return passcode

def lambda_handler(event, context):
    message = "submitted"
    print(event)
    info = json.loads(event['body'])['messages'][0]["unstructured"]["text"].split(",")
    if info[1] == "" or info[2] == "":
        message = "Please fill in the required fields!"
    #print(info[2])
    if len(info[2]) != 10:
        message = "The format is not valid!"
    photo_id = info[0]
    name = info[1].replace(" ", "-")
    phone = info[2]
    # store in "visitors"
    file = "/tmp/pic_"+photo_id+".jpg"
    bucket = "assignment2-b1"
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket, file)
    body = obj.get()['Body'].read()
    rekog = boto3.client('rekognition')
    index_face = rekog.index_faces(
        CollectionId = 'face_collection',
        Image={
            'Bytes' : body
        },
        ExternalImageId = name)
    #print(index_face)
    #print(index_face['FaceRecords'][0]['Face']['FaceId'])
    faceID = index_face['FaceRecords'][0]['Face']['FaceId']
    insert_visitor(faceID, name, phone, file, "assignment2-b1")
    # store in "passcodes"
    new_code = create_passcode()
    insert_passcode(faceID, new_code)
    # push to SNS queue
    #push_to_SNS(faceID, phone, new_code)
    phone="+1"+phone
    guest_message="Please visit https://assignment2-b1.s3.amazonaws.com/wp2.html?id="+faceID
    guest_message += " to enter your passcode: "+str(new_code)
    send_message(guest_message, phone)
    return {
        'headers':{
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': message
    }
