# MealieMate

MealieMate is a collection of Python scripts bundled in a service that integrate with [Mealie](https://github.com/hay-kot/mealie), [Home Assistant](https://www.home-assistant.io/), and [MQTT](https://mqtt.org/) to provide advanced meal planning, recipe tagging, and shopping list generation—powered by OpenAI GPT. Each script can be controlled via switches in Home Assistant, and logs its progress and feedback in several sensors.

*Disclaimer*: This is a project to help me learn different things, I am just sharing it openly to learn even more. 

---

## Features

1. **Recipe Tagger**  
   Uses GPT to classify your Mealie recipes with appropriate tags and categories automatically. The AI analyzes recipe ingredients and names to assign relevant tags from predefined categories.

2. **Ingredient Merger**  
   Identifies ingredients across recipes that are exact duplicates but have different names (like "heavy cream" and "cream 15% fat", or "parmesan" and "parmeggiano"). Provides a standardized name and lists all recipes containing these ingredients for easier database cleanup.

3. **Meal Planner**  
   Generates structured, balanced meal plans based on Mealie recipes (tags and categories), user constraints, and existing plans. Follows specific rules like scheduling pizza on Fridays and ensuring nutritional balance.

4. **Shopping List Generator**  
   Consolidates ingredients from your upcoming meal plan into a single structured shopping list in Mealie. The AI intelligently combines similar items, standardizes quantities, and organizes by category for easier shopping.

5. **Mealplan Fetcher**
   Gets the mealplan for the next 7 days and makes it available in Home Assistant, including direct links to every recipe. Also generates a visually appealing image and publishes it via MQTT. This automatically creates an `image` entity in Home Assistant (e.g., `image.mealiemate_meal_plan_image`) for display. Other services can subscribe to the image topic (`mealiemate/mealplan_fetcher/mealplan_image/image`) to receive the raw PNG bytes.

6. **Neapolitan Pizza Calculator**  
   Calculates precise dough ingredients and fermentation schedules for Neapolitan-style pizza based on temperature and time parameters. Uses a scientific approach to adjust yeast quantities for consistent results.


---

## Integrations

### Mealie

The tools perform API requests to Mealie using HTTP. A token from your Mealie instance is required to authenticate. The integration handles recipe fetching, meal plan management, and shopping list creation.

### OpenAI GPT

The tools send relevant data and instructions to the `gpt-4o` model for processing. The integration includes retry logic, error handling, and optimized prompts for consistent results. An API token from OpenAI is needed to enable GPT functionality.

### Home Assistant

These scripts automatically register a new device named **"MealieMate"** in Home Assistant using **MQTT discovery**. They provide switches and sensors for configuring, triggering, and reading the output of each script. The integration includes:

- Switches to enable/disable each script
- Sensors to display script output and status
- Number inputs for configuration parameters
- Text inputs for user messages and preferences

### MQTT Image Publishing (via Mealplan Fetcher)

The Mealplan Fetcher plugin publishes the generated meal plan image as raw PNG bytes directly to the following MQTT topic: `mealiemate/mealplan_fetcher/mealplan_image/image`. Home Assistant uses this topic via the auto-discovered `image` entity, and other external services (like e-ink displays) can subscribe to this same topic to receive the image data.

---

## Home Assistant Configuration

For detailed YAML configurations to set up your Home Assistant dashboard with MealieMate, refer to the [Home Assistant Cards](doc/home_assistant_cards.md) documentation.


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
      USE_OPENROUTER: "false"
      OPENROUTER_API_KEY: "insert_here"
      OPENROUTER_MODEL: "deepseek/deepseek-r1-zero:free"
      HA_URL: "http://192.168.XX.XX:8123"
      HA_TOKEN: "insert_here"
      MQTT_BROKER: "192.168.XX.XX"
      MQTT_PORT: "1883"
    restart: unless-stopped
```

### Environment Variables

- **MEALIE_URL**
    - Base URL for your Mealie instance.
- **MEALIE_TOKEN**
    - Your Mealie API token.
- **OPENAI_API_KEY**
    - Your OpenAI API key for GPT calls (required if not using OpenRouter). If you want to use OpenRouter, leave this empty.
- **USE_OPENROUTER** (optional)
    - Set to "true" to use OpenRouter instead of OpenAI. Defaults to "false".
- **OPENROUTER_API_KEY**
    - Your OpenRouter API key. Required when using OpenRouter.
- **OPENROUTER_MODEL** (optional)
    - The model to use with OpenRouter. Defaults to "deepseek/deepseek-r1-zero:free". See https://openrouter.ai/docs#models for a list of available models.
- **HA_URL**
    - Base URL for Home Assistant, if you're calling any of its services.
- **HA_TOKEN**
    - A Long-Lived Access Token for Home Assistant, if needed for updates.
- **MQTT_BROKER**
    - The IP address or hostname of your MQTT broker.
- **MQTT_PORT**
    - Port number of your MQTT broker (default 1883).

## Contributing

Contributions are welcome! Here's how you can help:

- Fork the repository and create a new branch for your feature or fix.
- Ensure your code follows the project's style and includes appropriate tests.
- Add or update documentation as necessary.
- Open a Pull Request with a clear description of changes.

You can refer to the [archictecture](doc/architecture.md) for further clarification of how Mealiemate is designed. 

Areas for improvement:

- Unit tests for core functionality
- Additional GPT-powered features
- UI improvements for Home Assistant integration
- Performance optimizations
- Documentation enhancements

## License

This project is licensed under the MIT License.

## Special Thanks

- To the Mealie community for their awesome recipe manager.
- To Home Assistant for making smart home integrations so powerful and flexible.
- And to all contributors who help make open-source projects thrive!
