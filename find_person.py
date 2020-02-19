import awscam
import cv2
import datetime
import greengrasssdk
import json
import os
import time

from botocore.session import Session
from threading import Thread
from threading import Timer

# Setup the S3 client
session = Session()
s3 = session.create_client("s3")
# s3_bucket = "deeplens-doorman-demo"
# s3_bucket = os.environ["BUCKET_NAME"]
s3_bucket = os.environ.get("BUCKET_NAME", "deeplens-doorman-demo")

# Create an AWS Greengrass core SDK client.
client = greengrasssdk.client("iot-data")

# The information exchanged between AWS IoT and the AWS Cloud has
# a topic and a message body.
# This is the topic that this code uses to send messages to the Cloud.
iotName = os.environ.get("AWS_IOT_THING_NAME", "deeplens-doorman")
iotTopic = "$aws/things/{}/infer".format(iotName)
_, frame = awscam.getLastFrame()
_, jpeg = cv2.imencode(".jpg", frame)
Write_To_FIFO = True


class FIFO_Thread(Thread):
    def __init__(self):
        """ Constructor. """
        Thread.__init__(self)

    def run(self):
        fifo_path = "/tmp/results.mjpeg"
        if not os.path.exists(fifo_path):
            os.mkfifo(fifo_path)
        f = open(fifo_path, "w")
        client.publish(topic=iotTopic, payload="Opened Pipe")
        while Write_To_FIFO:
            try:
                f.write(jpeg.tobytes())
            except IOError as e:
                continue


def greengrass_infinite_infer_run():
    try:
        modelPath = "/opt/awscam/artifacts/mxnet_deploy_ssd_resnet50_300_FP16_FUSED.xml"
        modelType = "ssd"
        input_width = 300
        input_height = 300
        max_threshold = 0.60  # raise/lower this value based on your conditions
        outMap = {
            1: "aeroplane",
            2: "bicycle",
            3: "bird",
            4: "boat",
            5: "bottle",
            6: "bus",
            7: "car",
            8: "cat",
            9: "chair",
            10: "cow",
            11: "dinning table",
            12: "dog",
            13: "horse",
            14: "motorbike",
            15: "person",
            16: "pottedplant",
            17: "sheep",
            18: "sofa",
            19: "train",
            20: "tvmonitor",
        }
        results_thread = FIFO_Thread()
        results_thread.start()

        # Send a starting message to the AWS IoT console.
        client.publish(topic=iotTopic, payload="Object detection starts now")

        # Load the model to the GPU (use {"GPU": 0} for CPU).
        mcfg = {"GPU": 1}
        model = awscam.Model(modelPath, mcfg)

        client.publish(topic=iotTopic, payload="Model loaded")

        ret, frame = awscam.getLastFrame()
        if ret == False:
            raise Exception("Failed to get frame from the stream")

        yscale = float(frame.shape[0] / input_height)
        xscale = float(frame.shape[1] / input_width)

        doInfer = True
        while doInfer:
            # Get a frame from the video stream.
            ret, frame = awscam.getLastFrame()

            # If you fail to get a frame, raise an exception.
            if ret == False:
                raise Exception("Failed to get frame from the stream")

            # Resize the frame to meet the  model input requirement.
            frameResize = cv2.resize(frame, (input_width, input_height))

            # Run model inference on the resized frame.
            inferOutput = model.doInference(frameResize)

            # Output the result of inference to the fifo file so it can be viewed with mplayer.
            parsed_results = model.parseResult(modelType, inferOutput)["ssd"]
            label = "{"
            for obj in parsed_results:
                if obj["prob"] > max_threshold:
                    xmin = int(xscale * obj["xmin"]) + int(
                        (obj["xmin"] - input_width / 2) + input_width / 2
                    )
                    ymin = int(yscale * obj["ymin"])
                    xmax = int(xscale * obj["xmax"]) + int(
                        (obj["xmax"] - input_width / 2) + input_width / 2
                    )
                    ymax = int(yscale * obj["ymax"])

                    # if a person was found, upload the target area to S3 for further inspection
                    if outMap[obj["label"]] == "person":
                        # get the person image
                        person = frame[ymin:ymax, xmin:xmax]

                        # create a s3 file key
                        s3_key = (
                            datetime.datetime.utcnow().strftime("%Y-%m-%d_%H_%M_%S.%f")
                            + ".jpg"
                        )
                        encode_param = [
                            int(cv2.IMWRITE_JPEG_QUALITY),
                            90,
                        ]  # 90% should be more than enough
                        _, jpg_data = cv2.imencode(".jpg", person, encode_param)
                        filename = (
                            "incoming/%s" % s3_key
                        )  # the guess lambda function is listening here
                        res = s3.put_object(
                            ACL="public-read",
                            Body=jpg_data.tostring(),
                            Bucket=s3_bucket,
                            Key=filename,
                        )
                        print(res.json())

                    # draw a rectangle around the designated area, and tell what label was found
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 165, 20), 4)
                    label += '"{}": {:.2f},'.format(outMap[obj["label"]], obj["prob"])
                    label_show = "{}:    {:.2f}%".format(
                        outMap[obj["label"]], obj["prob"] * 100
                    )
                    cv2.putText(
                        frame,
                        label_show,
                        (xmin, ymin - 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 165, 20),
                        4,
                    )

            label += '"null": 0.0'
            label += "}"
            client.publish(topic=iotTopic, payload=label)
            global jpeg
            ret, jpeg = cv2.imencode(".jpg", frame)

    except Exception as e:
        msg = "Test failed: " + str(e)
        client.publish(topic=iotTopic, payload=msg)

    # Asynchronously schedule this function to be run again in 15 seconds.
    Timer(15, greengrass_infinite_infer_run).start()


# Execute the function.
greengrass_infinite_infer_run()

# This is a dummy handler and will not be invoked.
# Instead, the code is executed in an infinite loop for our example.
def function_handler(event, context):
    return
