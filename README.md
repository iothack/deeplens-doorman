# deeplens-doorman

딥렌즈로 지나간 사람을 간지하여 슬랙에 알림을 줍니다.

딥렌즈에서 사람을 감지 하면, slck 에 사진을 올리고, 안면인식을 수행 합니다.
알지 못하는 사람이면 슬랙 사용자에서 선택 할수 있도록 합니다.
알고 있는 사람이라면 환영 문구를 출력합니다.

## 슬랙 설정

## 환경 변수

서울 리전에는 딥렌즈가 없으므로 제일 가까운 도쿄 리전을 선택 했습니다.
딥렌즈에서 사진을 업로드 할 버켓을 설정 합니다.

```bash
export AWSREGION="ap-northeast-1"
export BUCKET_NAME="deeplens-doorman-demo"
export SLACK_API_TOKEN="xoxb-xxx-xxx-xxx"
export SLACK_CHANNEL_ID="CU6UJ4XXX"
export REKOGNITION_COLLECTION_ID="doorman"
```

rekognition collection 을 생성 합니다.

```bash
# aws s3 mb s3://${BUCKET_NAME} --region ${AWSREGION}

aws rekognition create-collection --collection-id $REKOGNITION_COLLECTION_ID --region $AWSREGION
# aws rekognition delete-collection --collection-id $REKOGNITION_COLLECTION_ID --region $AWSREGION
```

# 개발 환경 및 배포 환경 설정

```bash
# pip install pyenv
# pyenv install 3.7.6
pyenv shell 3.7.6
sls plugin install -n serverless-python-requirements
sls deploy
```
