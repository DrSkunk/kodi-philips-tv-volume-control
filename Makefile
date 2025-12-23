ADDON_ID := script.philips-tv-volume-control
VERSION := $(shell python3 -c "import re, pathlib; text = pathlib.Path('addon.xml').read_text(); m = re.search(r'<addon[^>]*version=\\\"([^\\\"]+)\\\"', text); print(m.group(1) if m else '')")
BUILD_DIR := build
STAGING := $(BUILD_DIR)/$(ADDON_ID)
ZIP := $(BUILD_DIR)/$(ADDON_ID)-$(VERSION).zip

SRC_FILES := addon.xml \
	default.py \
	philips_tv.py \
	README.md \
	LICENSE

.PHONY: all clean zip

all: zip

zip: clean $(ZIP)

$(ZIP): $(SRC_FILES)
	@mkdir -p "$(STAGING)"
	@cp $(SRC_FILES) "$(STAGING)"/
	cd "$(BUILD_DIR)" && zip -r "$(notdir $@)" "$(ADDON_ID)"

clean:
	rm -rf "$(BUILD_DIR)"
