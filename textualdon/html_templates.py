html_success_msg = """
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #333;
        }
        div {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 {
            margin-top: 0;
            color: #0078d4;
        }
        p {
            margin-bottom: 0;
            font-size: 1.1em;
        }
    </style>
</head>
<body>
    <div>
        <h1>TextualDon is authorized.</h1>
        <p>You can close this window now.</p>
    </div>
</body>
</html>
"""

html_failure_msg = """
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #333;
        }
        div {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 2px solid #ff4d4d; /* Red border for emphasis */
        }
        h1 {
            margin-top: 0;
            color: #ff1a1a; /* Bright red for the error title */
        }
        p {
            margin-bottom: 0;
            font-size: 1.1em;
            color: #990000; /* Darker red for the message */
        }
    </style>
</head>
<body>
    <div>
        <h1>Authorization Error</h1>
        <p>No code received. Please try again.</p>
    </div>
</body>
</html>
"""