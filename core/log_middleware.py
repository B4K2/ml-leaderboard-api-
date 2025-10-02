import logging
import json

# Get an instance of a logger
logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log the request details before the view is called
        log_data = {
            'method': request.method,
            'path': request.path,
            'headers': dict(request.headers),
        }

        # Try to log the request body, decoding it if it's JSON
        if request.body:
            try:
                log_data['body'] = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                log_data['body'] = "Non-JSON body or decoding error"
        else:
            log_data['body'] = "No body"

        logger.info(f"INCOMING REQUEST: {json.dumps(log_data, indent=2)}")

        # Let the request continue to the view
        response = self.get_response(request)

        # You could also log the response here if you wanted
        
        return response