

tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_short_clip",
            "description": "Select a moment from a podcast/video to generate a short engaging clip for social media.",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_id": {
                        "type": "string",
                        "description": "Unique ID of the podcast or video file."
                    },
                    "language": {
                        "type": "string",
                        "description": "The language of the content (e.g. 'en', 'ru')."
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["tiktok", "youtube", "instagram"],
                        "description": "Target platform for clip formatting."
                    }
                },
                "required": ["media_id", "platform"]
            }
        }
    }
]
