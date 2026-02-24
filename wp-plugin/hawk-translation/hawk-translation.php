<?php
/**
 * Plugin Name: Hawk News Service translation
 * Description: Translate posts via the Hawk News Service API.
 * Version: 1.0.0
 * Author: Center for Cooperative Media
 */

if (!defined('ABSPATH')) exit;

define('HAWK_PLUGIN_DIR', plugin_dir_path(__FILE__));

require_once HAWK_PLUGIN_DIR . 'settings.php';
require_once HAWK_PLUGIN_DIR . 'translate-meta-box.php';

register_activation_hook(__FILE__, function () {
    add_option('hawk_api_key', '');
    add_option('hawk_api_base_url', 'https://api.hawknewsservice.org/v1');
    add_option('hawk_default_tier', 'instant');
    add_option('hawk_default_languages', ['es']);
});
