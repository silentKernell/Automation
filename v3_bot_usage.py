# 1. Fix for first-letter issue (now types properly)
bot.open_chat("Contact Name")
bot.send_message("This will be typed character by character")

# 2. Broadcast to CSV
contacts = bot.load_contacts_from_csv("my_contacts.csv")
bot.broadcast_to_contacts(contacts, "Hello everyone!", identifier_field='name')

# 3. Get linking code
code = bot.get_linking_code()  # Shows: "ABCD-1234"

# 4. Watch statuses
def my_handler(status):
    print(f"New status from: {status['contact']}")
bot.start_status_watcher(callback=my_handler)

# 5. Send high-quality media
bot.send_image_high_quality("photo.jpg", "Beautiful view!")