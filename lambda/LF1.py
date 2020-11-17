import logging
import boto3
import json
import random
import base64
import cv2
from botocore.exceptions import ClientError
from datetime import datetime

def check_call(lambda_name, time):
    db = boto3.resource('dynamodb')
    table = db.Table('lambda_trigger')
    info = table.get_item(Key={'lambda_name': lambda_name})
    if 'Item' not in info:
        return True
    correct = info["Item"]["call_timestamp"]
    curr = int(datetime.now().timestamp())
    if curr - int(correct) > time:
        return True
    return False

def update_call(lambda_name):
    db = boto3.resource('dynamodb')
    table = db.Table('lambda_trigger')
    curr = datetime.now().timestamp()
    response = table.put_item(
        Item={
            'lambda_name': lambda_name,
            'call_timestamp': int(curr)
        }
    )
    return response
    
def getGuest(faceId):
    db = boto3.resource('dynamodb')
    table = db.Table('visitors')
    info = table.get_item(Key={'faceID': faceId})
    if 'Item' not in info:
        return None
    else:
        return info

def insert_photo(faceID, photo):
    db = boto3.resource('dynamodb')
    table = db.Table("visitors")
    result = table.update_item(
        Key={
            'faceID': faceID
            },
            UpdateExpression="SET photos = list_append(photos, :i)",
            ExpressionAttributeValues={
        ':i': [{"objectKey": photo, "bucket": "assignment2-b1", "createdTimestamp": str(datetime.now())}],
        },
        ReturnValues="UPDATED_NEW")
    
def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True
    
def send_message(message, phone):
    client = boto3.client("sns")
    client.publish(MessageStructure='string', PhoneNumber=phone, Message=message)

def create_passcode():
    passcode = str(random.randint(1000, 9999))
    return passcode

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

def lambda_handler(event, context):
    #print("SOME RECORDS COME")
    print(event['Records'])
    for record in event['Records']:
        #Kinesis data is base64 encoded so decode here
        payload=base64.b64decode(record["kinesis"]["data"]).decode('utf-8')
        #print("Decoded payload: " + str(payload))
        info = json.loads(payload)
        print(info)
        if len(info["FaceSearchResponse"]) == 0:
            print("No face detected.")
        else:
            print("Face detected.")
            if not check_call("Assignment2-LF1", 10):
                print("Cold Down...")
                break
            else:
                print("Success call")
                update_call("Assignment2-LF1")
            kvs = boto3.client("kinesisvideo")
            endpoint = kvs.get_data_endpoint(
                APIName= "GET_MEDIA_FOR_FRAGMENT_LIST",
                StreamName='kvs1')['DataEndpoint']
            client = boto3.client('kinesis-video-archived-media',endpoint_url=endpoint)
            kvs_stream = client.get_media_for_fragment_list(
                StreamName='kvs1',
                Fragments=[
                    info["InputInformation"]["KinesisVideo"]["FragmentNumber"],
                ]
            )
            #print(kvs_stream)
            img_id = str(datetime.now()).replace(" ", "-")
            frame = kvs_stream['Payload'].read()
            stream_name="/tmp/stream_%s.avi" % img_id
            #print(frame)
            with open(stream_name, 'wb') as f:
                f.write(frame)
            f.close()
            cap = cv2.VideoCapture(stream_name)
            #print(cap.read())
            success, image = cap.read()
            count = 0
            prev = None
            while success:
                success, image = cap.read()
                count += 1
                #if image is None:
                #    image = prev
                #    break
                if image is not None and count > 50:
                    #print(image)
                    break
                if image is not None:
                    prev = image
            if image is None:
                image = prev
            if image is None:
                print(count)
                print("No frame was extracted.")
                continue
            file_name="/tmp/pic_%s.jpg" % img_id
            print(file_name)
            cv2.imwrite(file_name, image)
            cap.release()
            #cv2.destroyAllWindows()
            upload_file(file_name, "assignment2-b1")
            img_url = "https://assignment2-b1.s3.amazonaws.com/"+file_name
            #known = info["FaceSearchResponse"][0]["MatchedFaces"]
            for people in info["FaceSearchResponse"]:
                if len(people["MatchedFaces"]) == 0:
                    if not check_call("unknown", 20):
                        print("unknown cold down")
                        break
                    else:
                        update_call("unknown")
                        print("unknown sent")
                    message = "New face detected: " + img_url
                    message += " : visit https://assignment2-b1.s3.amazonaws.com/wp1.html?img=" + img_id
                    message += " to assign the visitor a one time posscode."
                    print(message)
                    send_message(message, "+16085040737")
                    
                else:
                    detected_faceID = people['MatchedFaces'][0]['Face']['FaceId']
                    print(detected_faceID)
                    guest = getGuest(detected_faceID)
                    if guest is None:
                        if not check_call("unknown", 20):
                            print("unknown cold down")
                            break
                        else:
                            update_call("unknown")
                            print("unknown sent")
                        message = "New face detected: " + img_url
                        message += " : visit https://assignment2-b1.s3.amazonaws.com/wp1.html?img=" + img_id
                        message += " to assign the visitor a one time posscode."
                        print(message)
                        send_message(message, "+16085040737")
                    else:
                        if not check_call(detected_faceID, 60):
                            print(detected_faceID+" cold down")
                            break
                        else:
                            update_call(detected_faceID)
                            print(detected_faceID+" sent")
                        new_code = create_passcode()
                        insert_passcode(detected_faceID, new_code)
                        message="Please visit https://assignment2-b1.s3.amazonaws.com/wp2.html?id="+detected_faceID
                        message += " to enter your passcode: "+str(new_code)
                        phone = guest["Item"]['phoneNumber']
                        phone="+1"+phone
                        send_message(message, phone)
                        insert_photo(detected_faceID, file_name)
       
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
