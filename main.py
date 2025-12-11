import os
import functions_framework
from flask import jsonify
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

DISCORD_PUBLIC_KEY = os.environ.get('DISCORD_PUBLIC_KEY')

@functions_framework.http
def hello_http(request):
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')

    if not signature or not timestamp:
        return 'Missing headers', 401

    if not DISCORD_PUBLIC_KEY:
        return 'Server Error: Public Key is missing', 500

    verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
    body = request.data.decode('utf-8')

    try:
        verify_key.verify(f'{timestamp}{body}'.encode(), bytes.fromhex(signature))
    except BadSignatureError:
        return 'Invalid request signature', 401

    req_json = request.get_json()
    interaction_type = req_json.get('type')

    # Type 1: PING
    if interaction_type == 1:
        return jsonify({'type': 1})

    # Type 2: COMMAND
    if interaction_type == 2:
        command_name = req_json['data']['name']
        
        # Command Registry (Simple if/elif for now - can be scalable later)
        if command_name == 'sns-x':
            from commands.sns_x.controller import SnsXController
            controller = SnsXController()
            return jsonify(controller.execute(req_json))
            
        elif command_name == 'sns-x-today':
            from commands.sns_x.controller import SnsXTodayController
            controller = SnsXTodayController()
            return jsonify(controller.execute(req_json))

        # Legacy/Test Command
        if command_name == 'test':
            return jsonify({
                'type': 4,
                'data': {'content': '🚀 GitHub連携からのデプロイ成功です！'}
            })

    return jsonify({'type': 4, 'data': {'content': 'コマンドが見つかりません'}})

