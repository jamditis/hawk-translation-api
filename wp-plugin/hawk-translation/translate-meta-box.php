<?php
add_action('add_meta_boxes', function () {
    add_meta_box('hawk-translate', 'Hawk translation', 'hawk_meta_box', 'post', 'side');
});

function hawk_meta_box($post) {
    $languages = [
        'es' => 'Spanish',
        'pt' => 'Portuguese',
        'ht' => 'Haitian Creole',
        'zh' => 'Chinese (Simplified)',
        'ko' => 'Korean',
        'ar' => 'Arabic',
        'fr' => 'French',
        'pl' => 'Polish',
        'hi' => 'Hindi',
        'ur' => 'Urdu',
    ];
    ?>
    <p><strong>Translate this post</strong></p>
    <select id="hawk-lang" style="width:100%;margin-bottom:8px;">
        <?php foreach ($languages as $code => $name): ?>
            <option value="<?php echo esc_attr($code); ?>"><?php echo esc_html($name); ?></option>
        <?php endforeach; ?>
    </select>
    <button type="button" id="hawk-submit" class="button" style="width:100%">Send for translation</button>
    <p id="hawk-status" style="margin-top:8px;font-size:12px;color:#666;"></p>

    <script>
    document.getElementById('hawk-submit').addEventListener('click', function() {
        var btn = this;
        var lang = document.getElementById('hawk-lang').value;
        var status = document.getElementById('hawk-status');
        btn.disabled = true;
        status.textContent = 'Submitting...';

        fetch(ajaxurl, {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams({
                action: 'hawk_translate',
                post_id: '<?php echo absint($post->ID); ?>',
                language: lang,
                nonce: '<?php echo wp_create_nonce('hawk_translate'); ?>'
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            btn.disabled = false;
            if (data.success) {
                status.style.color = '#0a6;';
                status.textContent = 'Submitted. Job: ' + data.data.job_id;
            } else {
                status.style.color = '#c33';
                status.textContent = 'Error: ' + (data.data.error || 'unknown error');
            }
        })
        .catch(function() {
            btn.disabled = false;
            status.style.color = '#c33';
            status.textContent = 'Request failed.';
        });
    });
    </script>
    <?php
}

add_action('wp_ajax_hawk_translate', function () {
    check_ajax_referer('hawk_translate', 'nonce');

    if (!current_user_can('edit_posts')) {
        wp_send_json_error(['error' => 'insufficient permissions']);
    }

    $post_id = absint($_POST['post_id']);
    $language = sanitize_text_field($_POST['language']);
    $post = get_post($post_id);

    if (!$post) {
        wp_send_json_error(['error' => 'post not found']);
    }

    $api_key = get_option('hawk_api_key');
    if (!$api_key) {
        wp_send_json_error(['error' => 'no API key configured']);
    }

    $base_url = get_option('hawk_api_base_url', 'https://api.hawknewsservice.org/v1');
    $tier = get_option('hawk_default_tier', 'instant');
    $content = apply_filters('the_content', $post->post_content);

    $response = wp_remote_post("$base_url/translate", [
        'timeout' => 15,
        'headers' => [
            'Authorization' => "Bearer $api_key",
            'Content-Type'  => 'application/json',
        ],
        'body' => wp_json_encode([
            'content'         => $content,
            'source_language' => 'en',
            'target_language' => $language,
            'tier'            => $tier,
            'metadata'        => [
                'headline'   => $post->post_title,
                'source_url' => get_permalink($post_id),
            ],
        ]),
    ]);

    if (is_wp_error($response)) {
        wp_send_json_error(['error' => $response->get_error_message()]);
    }

    $code = wp_remote_retrieve_response_code($response);
    $body = json_decode(wp_remote_retrieve_body($response), true);

    if ($code >= 400) {
        $msg = isset($body['detail']) ? $body['detail'] : "API returned $code";
        wp_send_json_error(['error' => $msg]);
    }

    wp_send_json_success(['job_id' => $body['job_id'] ?? null]);
});
