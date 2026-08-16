Downloads LinkedIn profile data via its Member API.

Profile picture is provided by LinkedIn, hence manually using the `profile_photo.jpg`.

Themes are based on official JSON Resume themes which appeared to be very complicated to use due to various Node.js-related issues. So the `jsonresume-theme-template` skill takes the theme npm package and creates HTML/CSS template based on that.

## Prerequisites

When downloading profile data, make sure `.env` file contains a value for `LINKEDIN_ACCESS_TOKEN` env variable.

