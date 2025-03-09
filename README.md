# MealieMate

MealieMate is a collection of Python scripts bundled in a service that integrate with [Mealie](https://github.com/hay-kot/mealie), [Home Assistant](https://www.home-assistant.io/), and [MQTT](https://mqtt.org/) to provide advanced meal planning, recipe tagging, and shopping list generation—powered by OpenAI GPT. Each script can be controlled via switches in Home Assistant, and logs its progress and feedback in several sensors.

*Disclaimer*: This is a project to help me learn different things, I am just sharing it openly to learn even more. 

---

## Features

1. **Recipe Tagger**  
   Uses GPT to classify your Mealie recipes with appropriate tags and categories automatically. The AI analyzes recipe ingredients and names to assign relevant tags from predefined categories.

2. **Meal Planner**  
   Generates structured, balanced meal plans based on Mealie recipes (tags and categories), user constraints, and existing plans. Follows specific rules like scheduling pizza on Fridays and ensuring nutritional balance.

3. **Shopping List Generator**  
   Consolidates ingredients from your upcoming meal plan into a single structured shopping list in Mealie. The AI intelligently combines similar items, standardizes quantities, and organizes by category for easier shopping.

4. **Mealplan Fetcher**  
   Gets the mealplan for the next 7 days and makes it available in Home Assistant, including direct links to every recipe. Also generates a visually appealing image that can be sent via Telegram using a bot.

5. **Neapolitan Pizza Calculator**  
   Calculates precise dough ingredients and fermentation schedules for Neapolitan-style pizza based on temperature and time parameters. Uses a scientific approach to adjust yeast quantities for consistent results.

---

## Technical Improvements

The codebase has been enhanced with several improvements:

- **Plugin Architecture**: Modular plugin system that allows for easy extension and maintenance. Each feature is implemented as a plugin with a clear interface.
- **Dependency Injection**: Service interfaces and a dependency injection container for better testability and loose coupling between components.
- **Type Hints**: Comprehensive type annotations throughout the codebase for better IDE support and static type checking.
- **Error Handling**: Robust error handling with specific error messages and appropriate fallbacks.
- **Logging**: Structured logging system for easier debugging and monitoring.
- **Code Organization**: Modular design with clear separation of concerns:
  - `core/`: Core interfaces and infrastructure
  - `plugins/`: Feature implementations as plugins
  - `services/`: Service implementations
  - `utils/`: Utility functions and helpers
- **Documentation**: Enhanced docstrings with detailed parameter descriptions and return value information.
- **Performance**: Optimized code for better performance and resource usage.

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

### Telegram

The Mealplan Fetcher can send generated meal plan images directly to a Telegram chat, providing an easy way to view your weekly meal plan on mobile devices.

---

## Home Assistant Configuration

For detailed YAML configurations to set up your Home Assistant dashboard with MealieMate, refer to the [Home Assistant Cards](home_assistant_cards.md) documentation.


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

- **MEALIE_URL**
    - Base URL for your Mealie instance.
- **MEALIE_TOKEN**
    - Your Mealie API token.
- **OPENAI_API_KEY**
    - Your OpenAI API key for GPT calls.
- **HA_URL**
    - Base URL for Home Assistant, if you're calling any of its services.
- **HA_TOKEN**
    - A Long-Lived Access Token for Home Assistant, if needed for updates.
- **MQTT_BROKER**
    - The IP address or hostname of your MQTT broker.
- **MQTT_PORT**
    - Port number of your MQTT broker (default 1883).
- **TG_BOT_TOKEN**
    - Telegram bot token for sending meal plan images.
- **TG_BOT_CHAT_ID**
    - Telegram chat ID to send messages to.

## Contributing

Contributions are welcome! Here's how you can help:

- Fork the repository and create a new branch for your feature or fix.
- Ensure your code follows the project's style and includes appropriate tests.
- Add or update documentation as necessary.
- Open a Pull Request with a clear description of changes.

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
- To OpenAI for providing the GPT models that power the intelligent features.
- And to all contributors who help make open-source projects thrive!
