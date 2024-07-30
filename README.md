# Uber Scraper

**Note: This project is outdated and no longer functional. It is kept for archival purposes only.**

## Description

This project was designed to scrape Uber ride prices for specific routes. It used Selenium WebDriver to automate the process of logging into Uber's website and retrieving price information for different ride types.

Example CSV file output is under the `csv/uber/` directory.

## Features

- Login to Uber's website (OTP verification should be manually entered through the terminal)
- Retrieval of price information for multiple ride types
- Saving of ride data to CSV files
- Proxy rotation support for avoiding IP bans

## Structure

- `uber_scraper.py`: Main script for scraping Uber prices
- `scraper.py`: Base scraper class with proxy rotation and retry functionality
- `csv/uber/`: Directory for storing scraped data in CSV format

## Setup

1. Install required packages:
```
pipenv install
```

2. Create a `.env` file in the project root directory with the following variables:

```
UBER_PHONE_NUMBER=your_phone_number
UBER_PASSWORD=your_password
```


## Usage

Run the main script:

```
python uber_scraper.py
```


## Disclaimer

This project is no longer maintained or functional due to changes in Uber's website structure and potential violations of their terms of service. It is provided for educational purposes only. Please respect Uber's terms of service and do not attempt to use this scraper without proper authorization.

## License

This project is licensed under the MIT License.