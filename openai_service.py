from openai import OpenAI
import os
from pydantic import BaseModel
from keys import OPENAI_KEY

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_KEY)

    
    async def get_completion_structured(self, prompt: str) -> CalendarEvent:
        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format=CalendarEvent,
            )
            return response.choices[0].message.parsed
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def get_completion(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    
    