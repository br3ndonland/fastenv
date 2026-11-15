import fastenv

dict(fastenv.parse_dotenv("PORT=8000 LABEL='local service'"))
# Output: {'PORT': '8000', 'LABEL': 'local service'}
