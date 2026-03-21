class StartRecording:
    """Service interface for starting video recording."""

    class Request:
        def __init__(self, take_id=None, start_time=None):
            self.take_id = take_id or ""
            self.start_time = start_time

    class Response:
        def __init__(self, success=None, filename=None, error=None):
            self.success = success if success is not None else False
            self.filename = filename or ""
            self.error = error or ""