<?php
add_action('admin_menu', function () {
    add_options_page(
        'Hawk translation settings',
        'Hawk translation',
        'manage_options',
        'hawk-translation',
        'hawk_settings_page'
    );
});

function hawk_settings_page() {
    if (isset($_POST['hawk_save'])) {
        check_admin_referer('hawk_settings');
        update_option('hawk_api_key', sanitize_text_field($_POST['hawk_api_key']));
        update_option('hawk_default_tier', sanitize_text_field($_POST['hawk_default_tier']));
        echo '<div class="updated"><p>Settings saved.</p></div>';
    }
    $api_key = get_option('hawk_api_key', '');
    $tier = get_option('hawk_default_tier', 'instant');
    ?>
    <div class="wrap">
        <h1>Hawk translation settings</h1>
        <form method="post">
            <?php wp_nonce_field('hawk_settings'); ?>
            <table class="form-table">
                <tr>
                    <th scope="row"><label for="hawk_api_key">API key</label></th>
                    <td><input type="text" id="hawk_api_key" name="hawk_api_key"
                               value="<?php echo esc_attr($api_key); ?>" size="50"
                               class="regular-text"></td>
                </tr>
                <tr>
                    <th scope="row"><label for="hawk_default_tier">Default tier</label></th>
                    <td>
                        <select id="hawk_default_tier" name="hawk_default_tier">
                            <option value="instant" <?php selected($tier, 'instant'); ?>>Instant (AI only)</option>
                            <option value="reviewed" <?php selected($tier, 'reviewed'); ?>>Reviewed (AI + human editor)</option>
                            <option value="certified" <?php selected($tier, 'certified'); ?>>Certified (professional translator)</option>
                        </select>
                    </td>
                </tr>
            </table>
            <input type="hidden" name="hawk_save" value="1">
            <?php submit_button('Save settings'); ?>
        </form>
    </div>
    <?php
}
