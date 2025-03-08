# MealieMate

MealieMate is a collection of Python scripts bundled in a service that integrate with [Mealie](https://github.com/hay-kot/mealie), [Home Assistant](https://www.home-assistant.io/), and [MQTT](https://mqtt.org/) to provide advanced meal planning, recipe tagging, and shopping list generation—powered by OpenAI GPT. Each script can be controlled via switches in Home Assistant, and logs its progress and feedback in several sensors.

*Disclaimer*: This is a project to help me learn different things, I am just sharing it openly to learn even more. 

---

## Features

1. **Recipe Tagger**  
   Uses GPT to classify your Mealie recipes with appropriate tags and categories automatically.

2. **Meal Planner**  
   Generates structured, balanced meal plans based on Mealie recipes (tags and categories), user constraints, and existing plans.

3. **Shopping List Generator**  
   Consolidates ingredients from your upcoming meal plan into a single structured shopping list in Mealie, which can be easily cleaned up looking at the pantry.

5. **Mealplan Fetcher**  
   Gets the mealplan for the next 7 days and makes it available in Home Assistant, including direct links to every recipe. Also generates an image that can be sent via Telegram using a bot. 

---

## Integrations

### Mealie

The tools perform API requests to Mealie using HTTP. A token from your Mealie instance is required to authenticate.

### ChatGPT

The tools send relevant data and instructions to the `gpt-4o` model for processing. An API token from OpenAI is needed to enable GPT functionality.

### Home Assistant

These scripts automatically register a new device named **"MealieMate"** in Home Assistant using **MQTT discovery**.  
They provide switches and sensors for configuring, triggering, and reading the output of each script. Some logs and feedback are posted as entity attributes (due to Home Assistant UI limitations). A future release may or may not include examples of cards for Home Assistant. 

---

## Usage

### Docker-compose

Below is a recommended Docker Compose configuration:

```yaml
version: "3.8"

services:
  mealiemate:
    container_name: "mealiemate"
    image: ghcr.io/xtract/mealiemate:latest
    environment:
      MEALIE_URL: "http://192.168.XX.XX:XXXX"
      MEALIE_TOKEN: "insert_here"
      OPENAI_API_KEY: "insert_here"
      HA_URL: "http://192.168.XX.XX:8123"
      HA_TOKEN: "insert_here"
      MQTT_BROKER: "192.168.XX.XX"
      MQTT_PORT: "1883"
      TG_BOT_TOKEN: "123456789:AAbbCCddEEffGGhhIIjjKKllMMnnOO00"
      TG_BOT_CHAT_ID: "123456789"
    restart: unless-stopped
```

### Environment Variables

- MEALIE_URL
    - Base URL for your Mealie instance.
- MEALIE_TOKEN
    - Your Mealie API token.
- OPENAI_API_KEY
    - Your OpenAI API key for GPT calls.
- HA_URL
    - Base URL for Home Assistant, if you’re calling any of its services.
- HA_TOKEN
    - A Long-Lived Access Token for Home Assistant, if needed for updates.
- MQTT_BROKER
    - The IP address or hostname of your MQTT broker.
- MQTT_PORT
    - Port number of your MQTT broker (default 1883).

## Contributing
As usual: 

- Fork the repository and create a new branch for your feature or fix.
- Open a Pull Request with a clear description of changes.

All improvements are welcome—better logging, new GPT logic, etc. 

Or, if the code hurts your eyes: 
Forget this repo and make proper tool of this; at the end of the day, I am just a hardware guy trying to put everything together!


## License

This project is licensed under the MIT License.

Special Thanks:

- To the Mealie community for their awesome recipe manager.
- To Home Assistant for making smart home integrations so powerful and flexible.
- And to all contributors who help make open-source projects thrive!
