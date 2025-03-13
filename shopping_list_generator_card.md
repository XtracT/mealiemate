## 1. Shopping List Generator Card

**Purpose:**  
This card is for the Shopping List Generator plugin. It provides a number input to specify how many days the shopping list should cover, displays feedback messages, and allows interactive selection of items to add to the shopping list. To change if the shopping list should be generated from today or tomorrow's meals, double tap or hold the icon.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 65%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 35%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Shopping List Generator
          secondary: |-
            {% if is_state('switch.mealiemate_include_today', 'on') %}
              Including today
            {% else %}
              Starting tomorrow
            {% endif %}
          icon: mdi:cart
          entity: switch.mealiemate_shopping_list_generator
          icon_color: >-
            {% if states('sensor.mealiemate_shopping_list_progress') | int ==
            100 %}
              green
            {% elif states('sensor.mealiemate_shopping_list_progress') | int > 0
            %}
              blue
            {% else %}
              grey
            {% endif %}
          hold_action:
            action: call-service
            service: switch.toggle
            target:
              entity_id: switch.mealiemate_include_today
            data: {}
          double_tap_action:
            action: call-service
            service: switch.toggle
            target:
              entity_id: switch.mealiemate_include_today
            data: {}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_shopping_list_days_required
          name: Days
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill_container: true
          layout: horizontal
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_shopping_list_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_shopping_list_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_shopping_list_progress")}}%';
            color: white;
          }

  # Feedback
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_shopping_list_feedback', 'full_text') }}
  # Item switches and continue button (only visible when plugin is running)
  - type: conditional
    conditions:
      - entity: switch.mealiemate_shopping_list_generator
        state: "on"
    card:
      type: vertical-stack
      cards:
        # Item switches (one per line)
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_1
              primary: "{{ state_attr('sensor.mealiemate_item_1', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_1', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_1', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_1', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
              
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_2
              primary: "{{ state_attr('sensor.mealiemate_item_2', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_2', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_2', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_2', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_3
              primary: "{{ state_attr('sensor.mealiemate_item_3', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_3', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_3', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_3', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
              
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_4
              primary: "{{ state_attr('sensor.mealiemate_item_4', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_4', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_4', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_4', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_5
              primary: "{{ state_attr('sensor.mealiemate_item_5', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_5', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_5', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_5', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
              
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_6
              primary: "{{ state_attr('sensor.mealiemate_item_6', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_6', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_6', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_6', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_7
              primary: "{{ state_attr('sensor.mealiemate_item_7', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_7', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_7', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_7', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
              
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_8
              primary: "{{ state_attr('sensor.mealiemate_item_8', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_8', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_8', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_8', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_9
              primary: "{{ state_attr('sensor.mealiemate_item_9', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_9', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_9', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_9', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }
          
            - type: custom:mushroom-template-card
              entity: switch.mealiemate_add_to_list_10
              primary: "{{ state_attr('sensor.mealiemate_item_10', 'full_text') }}"
              secondary: "{{ state_attr('sensor.mealiemate_item_10', 'quantity_info') }}"
              icon: >-
                {% if is_state('switch.mealiemate_add_to_list_10', 'on') %}
                  mdi:cart-plus
                {% else %}
                  mdi:cart-outline
                {% endif %}
              icon_color: >-
                {% if is_state('switch.mealiemate_add_to_list_10', 'on') %}
                  blue
                {% else %}
                  grey
                {% endif %}
              tap_action:
                action: toggle
              layout: horizontal
              fill: false
              multiline_primary: false
              card_mod:
                style: |
                  ha-card {
                    --mush-card-primary-font-size: 14px;
                    --mush-card-secondary-font-size: 12px;
                    --mush-card-padding: 8px;
                    margin-bottom: -8px;
                    min-height: 40px;
                  }

        # Continue button
        - type: custom:mushroom-entity-card
          entity: button.mealiemate_continue_to_next_batch
          name: Continue to Next Batch
          icon: mdi:arrow-right-circle
          icon_color: blue
          tap_action:
            action: toggle
          card_mod:
            style: |
              ha-card {
                margin: auto;
                display: block;
                width: fit-content;
              }
