from kafka import KafkaConsumer
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
import os, time
from io import BytesIO
from dotenv import load_dotenv
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# .env 파일을 로드하여 환경 변수 읽기
load_dotenv()

KAFKA_SERVER = os.getenv("KAFKA_SERVER")

# Kafka consumer 설정
consumer = KafkaConsumer(
    #'logs',
    bootstrap_servers=KAFKA_SERVER,
    group_id='log-consumer-group',
    enable_auto_commit=False,  # 수동 오프셋 커밋 설정
    auto_offset_reset='latest',  # 'earliest' 또는 'latest' 설정
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
# 여러 토픽을 구독
consumer.subscribe(['Login_log', 'Logout_log', 'KakaoLogin_log', 'KakaoLogout_log', 'Signup_log'])

# S3 클라이언트 설정
s3 = boto3.client('s3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ap-northeast-2"
    )

# Kafka 메시지 소비 및 S3 업로드 함수
# def consume_and_save_to_s3(batch_size=100, timeout=10):
#     log_messages = []  # 수집된 메시지를 저장
#     start_time = time.time()  # 시작 시간 기록

#     while True:
#         try:
#             # Kafka 메시지 폴링
#             records = consumer.poll(timeout_ms=500)
#             logger.debug(f"Kafka에서 {len(records)}개의 토픽 데이터를 폴링함.")

#             # 폴링된 메시지 처리
#             for topic_partition, messages in records.items():
#                 for message in messages:
#                     try:
#                         # 메시지 추가 및 로그
#                         log_messages.append(message.value)
#                         logger.info(f"토픽: {topic_partition.topic}, 메시지: {message.value}")

#                     except json.JSONDecodeError as e:
#                         logger.error(f"메시지 디코딩 오류: {e}, 메시지: {message.value}")
#                     except Exception as e:
#                         logger.error(f"메시지 처리 중 예외 발생: {e}, 메시지: {message.value}")

#             # 10초 또는 배치 크기 확인
#             current_time = time.time()
#             if len(log_messages) >= batch_size or (current_time - start_time) >= timeout:
#                 if log_messages:
#                     try:
#                         # DataFrame 변환
#                         df = pd.json_normalize(log_messages)
#                         # Parquet 파일 변환
#                         table = pa.Table.from_pandas(df)
#                         buffer = BytesIO()
#                         pq.write_table(table, buffer)
#                         buffer.seek(0)

#                         # S3 업로드
#                         timestamp = time.strftime("%Y-%m-%d_%H-%M")
#                         topic_name = messages[0].topic if messages else "unknown_topic"
#                         response = s3.put_object(
#                             Bucket='t1-tu-data',
#                             Key=f'{topic_name}/{timestamp}.parquet',
#                             Body=buffer
#                         )
#                         if response['ResponseMetadata']['HTTPStatusCode'] == 200:
#                             logger.info(f"S3 업로드 성공: {topic_name}/{timestamp}.parquet")
#                         else:
#                             logger.error(f"S3 업로드 실패: {response}")

#                     except Exception as e:
#                         logger.error(f"S3 업로드 또는 변환 중 예외 발생: {e}")

#                     # 배치 처리 후 초기화
#                     log_messages = []
#                     start_time = time.time()  # 타임아웃 리셋

#             # 메시지를 처리한 후 수동으로 오프셋 커밋
#             try:
#                 consumer.commit()
#             except Exception as e:
#                 logger.error(f"오프셋 커밋 중 오류 발생: {e}")

#             # 루프 딜레이 (너무 빠른 소비 방지)
#             time.sleep(0.5)

#         except KeyboardInterrupt:
#             logger.info("프로그램이 중단되었습니다.")
#             break
#         except Exception as e:
#             logger.error(f"소비 루프 중 예외 발생: {e}")

# Kafka 메시지 소비 및 S3 업로드 함수
###########변경필요##############
def consume_and_save_to_s3(batch_size=100, timeout=10):
    log_messages = []  # 수집된 메시지를 저장
    start_time = time.time()  # 시작 시간 기록

    while True:
        try:
            # Kafka 메시지 폴링
            records = consumer.poll(timeout_ms=500)
            logger.debug(f"Kafka에서 {len(records)}개의 토픽 데이터를 폴링함.")
            
            if not records:
                logger.warning("Kafka에서 가져온 메시지가 없습니다.")
                continue  # 메시지가 없으면 다음 반복

            # 폴링된 메시지 처리
            for topic_partition, messages in records.items():
                for message in messages:
                    try:
                        log_messages.append(message.value)
                        logger.info(f"토픽: {topic_partition.topic}, 메시지: {message.value}")
                    except Exception as e:
                        logger.error(f"메시지 처리 중 예외 발생: {e}, 메시지: {message.value}")

            # 배치 또는 타임아웃 조건 확인
            current_time = time.time()
            if len(log_messages) >= batch_size or (current_time - start_time) >= timeout:
                if log_messages:
                    try:
                        # 업로드 전 데이터 출력
                        logger.info(f"업로드할 배치 데이터:\n{log_messages}")

                        # DataFrame 변환
                        df = pd.json_normalize(log_messages)
                        logger.info(f"DataFrame:\n{df.head()}")

                        # Parquet 파일 변환
                        table = pa.Table.from_pandas(df)
                        buffer = BytesIO()
                        pq.write_table(table, buffer)
                        buffer.seek(0)

                        # S3 업로드
                        timestamp = time.strftime("%Y-%m-%d_%H-%M")
                        topic_name = messages[0].topic if messages else "unknown_topic"
                        response = s3.put_object(
                            Bucket='t1-tu-data',
                            Key=f'{topic_name}/{timestamp}.parquet',
                            Body=buffer
                        )
                        logger.info(f"S3 업로드 응답: {response}")

                        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                            logger.info(f"S3 업로드 성공: {topic_name}/{timestamp}.parquet")
                        else:
                            logger.error(f"S3 업로드 실패: {response}")

                    except Exception as e:
                        logger.error(f"S3 업로드 중 예외 발생: {e}")

                    # 초기화
                    log_messages = []
                    start_time = time.time()

            # 메시지 오프셋 커밋
            try:
                consumer.commit()
            except Exception as e:
                logger.error(f"오프셋 커밋 중 오류 발생: {e}")

            time.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("프로그램이 중단되었습니다.")
            break
        except Exception as e:
            logger.error(f"소비 루프 중 예외 발생: {e}")




if __name__ == '__main__':
    consume_and_save_to_s3(batch_size=100, timeout=10)
