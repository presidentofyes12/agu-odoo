#!/bin/bash
set -e  # Exit on error

export RESET="$1"
export GITLAB_EMAIL="$2"
export NOSTR_PUBKEY="$3"
export NOSTR_PRIVKEY="$4"
export GITLAB_URL="$5"

# Check if variables are set
if [ -z "$GITLAB_EMAIL" ] || [ -z "$NOSTR_PUBKEY" ] || [ -z "$NOSTR_PRIVKEY" ]; then
    echo "Error: Required environment variables not set"
    exit 1
fi

# Debug output
echo "Starting script with RESET=${RESET}"

# Handle reset flag before any operations
if [ "$RESET" = "reset" ]; then
    echo "WARNING: This will RESET all of GitLab's current configurations!"
    echo "You have 10 seconds to cancel this operation (CTRL-C)"
    echo "Waiting..."
    sleep 10
    
    echo "Starting GitLab reset process..."
    
    # Stop GitLab first
    echo "Stopping GitLab services..."
    sudo gitlab-ctl stop || true
    
    echo "Cleaning up existing swap files..."
    if swapon --show | grep -q /swapfile2; then
        sudo swapoff /swapfile2 || true
    fi
    if [ -f /swapfile2 ]; then
        sudo rm -f /swapfile2 || true
    fi
    if swapon --show | grep -q /swapfile; then
        sudo swapoff /swapfile || true
    fi
    if [ -f /swapfile ]; then
        sudo rm -f /swapfile || true
    fi
    
    # Remove GitLab packages first
    echo "Removing GitLab packages..."
    sudo apt-get remove --purge -y gitlab-ce || true
    sudo apt-get remove --purge -y gitlab-ee || true
    sudo apt-get remove --purge -y gitlab-rails || true
    sudo apt-get remove --purge -y gitlab-rake || true
    sudo apt-get remove --purge -y gitlab-ctl || true
    
    # Remove GitLab directories
    echo "Removing GitLab directories..."
    sudo rm -rf /etc/gitlab || true
    sudo rm -rf /var/opt/gitlab || true
    sudo rm -rf /var/log/gitlab || true
    sudo rm -rf /opt/gitlab /var/cache/gitlab || true
    sudo rm -rf /etc/apt/sources.list.d/gitlab* || true
    
    # Clean up
    echo "Cleaning up..."
    sudo apt-get clean
    sudo apt-get autoremove -y
    sudo rm -rf /etc/sv/gitlab* /etc/service/gitlab*
    
    # Now try to set up swap
    echo "Setting up swap space..."
    sudo fallocate -l 2G /swapfile2 || echo "Failed to create swap file, continuing anyway..."
    if [ -f /swapfile2 ]; then
        sudo chmod 600 /swapfile2
        sudo mkswap /swapfile2
        sudo swapon /swapfile2
        sudo swapon --show
    fi
    
    # Add GitLab repository
    echo "Adding GitLab repository..."
    curl -fsSL https://packages.gitlab.com/install/repositories/gitlab/gitlab-ee/script.deb.sh | sudo bash
    sudo apt update
    
    echo "Reset complete. Continuing with fresh installation..."
    sleep 3

elif [ -z "$RESET" ]; then
    echo "You can run the program with the 'reset' flag to completely reset the GitLab configuration."
    echo "Usage: ./gitlab_setup.sh reset"
    sleep 10
else
    echo "Reset flag not provided. Program will execute as normal."
    sleep 10
fi

# Add additional swap space if needed
if [ "$RESET" != "reset" ]; then
    echo "Adding 2GB of swap space..."
    if [ ! -f /swapfile2 ]; then
        sudo fallocate -l 2G /swapfile2
        sudo chmod 600 /swapfile2
        sudo mkswap /swapfile2
        sudo swapon /swapfile2
    else
        echo "Swap file already exists, skipping creation"
    fi
fi

# Install required packages
sudo apt-get update
sudo apt-get install -y curl openssh-server ca-certificates tzdata perl git
sudo apt-get install -y postfix

# Install and configure GitLab
sudo GITLAB_ROOT_EMAIL="$GITLAB_EMAIL" GITLAB_ROOT_PASSWORD="$NOSTR_PRIVKEY" EXTERNAL_URL="$GITLAB_URL" apt install gitlab-ee

# Generate and configure SSH keys for GitLab access
if [ ! -f "$HOME/.ssh/id_rsa" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -C "$GITLAB_EMAIL" -f "$HOME/.ssh/id_rsa" -N ""
    echo "Adding SSH key to GitLab..."
    curl --header "PRIVATE-TOKEN: $token" --data-urlencode "title=gitlab_key" --data-urlencode "key=$(cat $HOME/.ssh/id_rsa.pub)" "$GITLAB_URL/api/v4/user/keys"
fi

# Configure GitLab
sudo gitlab-rake gitlab:check

# Backup and update configuration
sudo cp /etc/gitlab/gitlab.rb /etc/gitlab/gitlab.rb.backup

# Increase service timeouts
echo "Configuring GitLab service timeouts..."
echo -e "\ngitlab_workhorse['shutdown_timeout'] = '120s'" | sudo tee -a /etc/gitlab/gitlab.rb
echo -e "gitlab_workhorse['auth_socket'] = '/var/opt/gitlab/gitlab-rails/sockets/gitlab.socket'" | sudo tee -a /etc/gitlab/gitlab.rb
echo -e "prometheus['listen_address'] = 'localhost:9229'" | sudo tee -a /etc/gitlab/gitlab.rb

# Update GitLab configuration for Puma
if ! grep -q "^external_url" /etc/gitlab/gitlab.rb; then
    echo -e "\nexternal_url 'http://localhost:8080'" | sudo tee -a /etc/gitlab/gitlab.rb
fi
if ! grep -q "^puma\['port'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Disable Puma from binding to a TCP port\npuma['port'] = nil" | sudo tee -a /etc/gitlab/gitlab.rb
fi
if ! grep -q "^puma\['listen'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Ensure Puma only binds to a Unix socket\npuma['listen'] = '/var/opt/gitlab/gitlab-rails/sockets/gitlab.socket'" | sudo tee -a /etc/gitlab/gitlab.rb
fi
if ! grep -q "^puma\['worker_processes'\]" /etc/gitlab/gitlab.rb; then
    echo -e "\n# Adjust the number of workers based on system resources\npuma['worker_processes'] = 2" | sudo tee -a /etc/gitlab/gitlab.rb
fi

# Reconfigure and restart GitLab
echo -e "\nReconfiguring GitLab..."
sudo gitlab-ctl reconfigure
echo -e "\nRestarting GitLab services..."
sudo gitlab-ctl restart

# Wait for GitLab to be ready
echo "Waiting for GitLab to be ready..."
until curl --output /dev/null --silent --head --fail "$GITLAB_URL"; do
    printf '.'
    sleep 10
done

# Create the user account first
sudo gitlab-rails runner "
begin
  # First check if email is already in use
  if User.find_by_email('${GITLAB_EMAIL}')
    puts 'Email already exists, attempting to use existing user'
    user = User.find_by_email('${GITLAB_EMAIL}')
  else
    # Create new user with all required fields
    user = User.new(
      username: '${NOSTR_PUBKEY}',
      email: '${GITLAB_EMAIL}',
      password: '${NOSTR_PRIVKEY}',
      password_confirmation: '${NOSTR_PRIVKEY}',
      name: 'GitLab User',  # Adding required name field
      skip_confirmation: true
    )
    user.admin = true
    
    # Create namespace for the user
    namespace = Namespace.new(
      name: user.username,
      path: user.username,
      owner: user
    )
    
    if namespace.save
      user.namespace = namespace
      if user.save
        puts 'User created successfully'
      else
        puts 'Error creating user:'
        puts user.errors.full_messages
        exit 1
      end
    else
      puts 'Error creating namespace:'
      puts namespace.errors.full_messages
      exit 1
    end
  end
rescue => e
  puts 'Error:'
  puts e.message
  exit 1
end"

# Create access token for Git operations
echo "Creating access token..."
LOG_FILE="/tmp/gitlab_token_creation.log"
token=$(sudo gitlab-rails runner "
begin
  puts 'Starting token creation...'
  user = User.find_by_email('${GITLAB_EMAIL}')
  
  puts 'Found user: ' + user.inspect
  
  token = PersonalAccessToken.new(
    user: user,
    name: 'Repository setup token',
    scopes: ['api', 'read_user', 'read_repository', 'write_repository'],
    expires_at: nil
  )
  
  puts 'Token object created: ' + token.inspect
  
  if token.save
    puts 'Token saved successfully: ' + token.token
  else
    puts 'Token save failed:'
    puts token.errors.full_messages
    puts token.errors.inspect
  end
rescue => e
  puts 'Exception occurred:'
  puts e.message
  puts e.backtrace
end" 2>&1 | sudo tee "$LOG_FILE")

echo "Token creation log saved to $LOG_FILE"

if [ -z "$token" ]; then
    echo "Failed to create access token"
    exit 1
fi

# Clone and push Sourcegraph/Cody repository
echo "Cloning and pushing Sourcegraph/Cody repository..."
WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"

# Clone the repository from GitHub
git clone https://github.com/sourcegraph/cody.git
cd cody

# Configure Git for GitLab
git config --global user.email "$GITLAB_EMAIL"
git config --global user.name "$NOSTR_PUBKEY"

# Create a new repository in GitLab via API
curl --header "PRIVATE-TOKEN: $token" \
     --data "name=cody&visibility=private" \
     "$GITLAB_URL/api/v4/projects"

# Add GitLab remote and push the repository using HTTP authentication
git remote remove origin
git_url=$(echo "$GITLAB_URL" | sed 's|http://||')
git remote add origin "http://root:${NOSTR_PRIVKEY}@${git_url}/root/cody.git"
git push -u origin --all

# Cleanup
cd ..
rm -rf "$WORK_DIR"

# Remove additional swap space after script completion
sudo swapoff /swapfile2
sudo rm /swapfile2

echo "Repository setup complete!"
echo "You can access Gitlab at $GITLAB_URL."

sleep 10

# sudo xdg-open "$GITLAB_URL" || true
