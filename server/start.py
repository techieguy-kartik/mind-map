import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()
if __name__=='__main__':
    uvicorn.run('server.app:app',host=os.getenv('ATLAS_HOST','127.0.0.1'),port=int(os.getenv('ATLAS_PORT','8000')),workers=1)
