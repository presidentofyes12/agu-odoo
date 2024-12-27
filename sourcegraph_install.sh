SOURCEGRAPHKEY = $1

sudo curl -L https://sourcegraph.com/.api/src-cli/src_linux_amd64 -o /usr/local/bin/src
sudo chmod +x /usr/local/bin/src
sudo src

# Add external_url if it doesn't exist
if ! grep -q "^external_url" /etc/gitlab/gitlab.rb; then
    echo -e "\nexternal_url 'http://localhost:8080'" | sudo tee -a /etc/gitlab/gitlab.rb
fi

# Add puma settings if they don't exist
if ! grep -q "^puma\['port'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Disable Puma from binding to a TCP port\npuma['port'] = nil" | sudo tee -a /etc/gitlab/gitlab.rb
fi

if ! grep -q "^puma\['listen'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Ensure Puma only binds to a Unix socket\npuma['listen'] = '/var/opt/gitlab/gitlab-rails/sockets/gitlab.socket'" | sudo tee -a /etc/gitlab/gitlab.rb
fi

if ! grep -q "^puma\['worker_processes'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Adjust the number of workers based on system resources\npuma['worker_processes'] = 2" | sudo tee -a /etc/gitlab/gitlab.rb
fi

if ! grep -q "^gitlab_rails\[\'sourcegraph_enabled\'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Sourcegraph integrations\ngitlab_rails['sourcegraph_enabled'] = true" | sudo tee -a /etc/gitlab/gitlab.rb
fi

if ! grep -q "^gitlab_rails\[\'sourcegraph_url\'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Sourcegraph integrations\ngitlab_rails['sourcegraph_url'] = 'http://localhost:7080'" | sudo tee -a /etc/gitlab/gitlab.rb
fi

if ! grep -q "^gitlab_rails\[\'sourcegraph_public_token\'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Sourcegraph integrations\ngitlab_rails['sourcegraph_public_token'] = '$SOURCEGRAPHKEY'" | sudo tee -a /etc/gitlab/gitlab.rb
fi

sudo docker run --publish 7080:7080 --publish 127.0.0.1:3370:3370 --rm --volume ~/.sourcegraph/config:/etc/sourcegraph --volume ~/.sourcegraph/data:/var/opt/sourcegraph sourcegraph/server:5.2.3
