import json, os, django
from confluent_kafka import Consumer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

consumer1 = Consumer({
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVER'),
    'security.protocol': 'SASL_SSL',
    'sasl.username': os.environ.get('KAFKA_USERNAME'),
    'sasl.password': os.environ.get('KAFKA_PASSWORD'),
    'sasl.mechanism': 'PLAIN',
    'group.id': 'messages_group',
    'auto.offset.reset': 'earliest'
})
consumer1.subscribe(['messages'])

while True:
    msg1 = consumer1.poll(1.0)

    if msg1 is None:
        continue
    if msg1.error():
        print(f"Error: {msg1.error()}")
        continue

    topic1 = msg1.topic()
    value1 = msg1.value()
    print(f"Message: {msg1}")

#     print("Received message: {}".format(msg.value()))

    # topic = msg.topic()
    # value = msg.value()

    # if topic == 'transactions':
    #     # execute logic for user_registered event
    #     if msg.key() == b'"order_created"':
    #         print('Add transaction here')
    #         print(json.loads(value))
    #         pass

consumer1.close()