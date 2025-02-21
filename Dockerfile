FROM python:3.12-alpine

WORKDIR /app

#RUN apk add --no-cache gcc musl-dev python3-dev libffi-dev

# Ensure logs are immediately flushed to stdout
ENV PYTHONUNBUFFERED=1

# Copy the Python scripts
COPY . .

# Generate requirements.txt from the script
#RUN pipreqs . --force

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
