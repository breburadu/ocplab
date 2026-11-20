<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>
    <?php
    $titleFile = 'title.txt';
    if (file_exists($titleFile)) {
        echo htmlspecialchars(file_get_contents($titleFile));
    } else {
        echo "Adolescentul – O Provocare"; // Fallback title
    }
    ?>
</title>
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/5.5.0/css/bootstrap.min.css">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<link rel="icon" href="fav.webp" type="image/webp">
<style>
    body {
        font-family: 'Poppins', sans-serif;
        background-color: #F8F9FA;
        color: #212529;
    }
    .hero-section {
        background: url('event.jpg') no-repeat center center/cover;
        height: 75vh;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        text-shadow: 0 2px 4px rgba(0,0,0,0.6);
    }
    .hero-section h1 {
        font-weight: 600;
        font-size: 2.5rem;
        padding: 0 20px;
        text-align: center;
    }
    .content-section, .event-date-section, .register-section, .author-info {
        margin: -5rem auto 2rem;
        padding: 2rem;
        background: white;
        border-radius: 12px;
        box-shadow: 0 6px 10px rgba(0,0,0,0.1);
        max-width: 800px;
        width: calc(100% - 40px);
    }
    .event-info {
        color: #4CAF50;
        margin-bottom: 1rem;
    }
    .btn-primary {
        background-color: #AED6F1;
        color: #333;
        font-weight: bold;
        border: none;
        width: 100%;
        padding: 12px;
    }
    .form-group {
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .form-group label {
        margin-bottom: 0.5rem;
    }
    @media (min-width: 768px) {
        .form-group {
            flex-direction: row;
            justify-content: space-between;
            align-items: center;
        }
        .form-group label {
            flex-basis: 30%;
            margin-bottom: 0;
            text-align: right;
            padding-right: 20px;
        }
        .form-group input {
            flex-basis: 70%;
        }
        .register-form {
            max-width: 600px;
            margin: 0 auto;
        }
        .btn-primary {
            width: auto;
            align-self: flex-start;
        }
    }
    .disclaimer {
        text-align: center;
        margin-top: 20px;
        font-size: 14px;
    }
</style>
<script>
    // JavaScript for enhanced form validation
    function validateForm() {
        const name = document.forms["registerForm"]["name"].value;
        const email = document.forms["registerForm"]["email"].value;
        const phone = document.forms["registerForm"]["telephone"].value;
        const emailPattern = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
        const phonePattern = /^[0-9\s\-+]+$/;

        if (name === "") {
            alert("Numele este obligatoriu.");
            return false;
        }
        if (!emailPattern.test(email)) {
            alert("Introduceți un email valid.");
            return false;
        }
        if (!phonePattern.test(phone)) {
            alert("Introduceți un număr de telefon valid.");
            return false;
        }
        return true;
    }

    // JavaScript to load the disclaimer or GDPR content into a styled popup
    function showPopup(file, title) {
        fetch(file)
            .then(response => response.text())
            .then(data => {
                let popupWindow = window.open("", title, "width=600,height=400");
                popupWindow.document.write(`
                    <html>
                    <head>
                        <title>${title}</title>
                        <style>
                            body {
                                font-family: 'Poppins', sans-serif;
                                background-color: #f4f4f4;
                                margin: 0;
                                padding: 20px;
                                color: #333;
                            }
                            .container {
                                max-width: 600px;
                                margin: 0 auto;
                                background-color: #fff;
                                padding: 20px;
                                border-radius: 8px;
                                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                            }
                            h1 {
                                font-size: 24px;
                                margin-bottom: 20px;
                                color: #4CAF50;
                                text-align: center;
                            }
                            p {
                                font-size: 16px;
                                line-height: 1.5;
                            }
                            .footer {
                                text-align: center;
                                margin-top: 20px;
                                font-size: 14px;
                                color: #666;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>${title}</h1>
                            <p>${data.replace(/\n/g, '<br>')}</p>
                            <div class="footer">
                                <p>&copy; 2024 Laura Elena Busuioc</p>
                            </div>
                        </div>
                    </body>
                    </html>
                `);
                popupWindow.document.close();
            })
            .catch(error => {
                alert('Nu s-a putut încărca conținutul.');
            });
    }
</script>
</head>
<body>

<section class="hero-section">
    <h1>
        <?php
        $motoFile = 'eventmoto.txt';
        if (file_exists($motoFile)) {
            echo htmlspecialchars(file_get_contents($motoFile));
        } else {
            echo "Adolescentul – O Provocare"; // Fallback content
        }
        ?>
    </h1>
</section>

<div class="container">
    <section class="content-section">
        <?php
        $filename = "content.txt";
        if (file_exists($filename)) {
            echo nl2br(file_get_contents($filename));
        } else {
            echo "<p>Fișierul de conținut nu a fost găsit.</p>";
        }
        ?>
    </section>

    <section class="event-date-section">
        <?php
        $dateFile = 'event_date.txt';
        $priceFile = 'event_price.txt';
        if (file_exists($dateFile)) {
            $eventDate = file_get_contents($dateFile);
            $formattedDate = substr($eventDate, 0, 2) . '-' . substr($eventDate, 2, 2) . '-' . substr($eventDate, 4);
            echo "<h2 class='event-info'>Data evenimentului: $formattedDate</h2>";
        } else {
            echo "<h2>Data evenimentului nu a fost găsită.</h2>";
        }
        if (file_exists($priceFile)) {
            $eventPrice = file_get_contents($priceFile);
            echo "<h2 class='event-info'>Prețul evenimentului: $eventPrice RON</h2>";
        } else {
            echo "<h2>Prețul evenimentului nu a fost găsit.</h2>";
        }
        ?>
    </section>

    <section class="register-section">
        <h2>Înscrie-te acum!</h2>
        
        <form name="registerForm" action="register.php" method="post" class="register-form" onsubmit="return validateForm()">
            <div class="form-group">
                <label for="name">Numele tău:</label>
                <input type="text" name="name" id="name" class="form-control" placeholder="Numele tău" required aria-required="true">
            </div>
            <div class="form-group">
                <label for="email">Emailul tău:</label>
                <input type="email" name="email" id="email" class="form-control" placeholder="Emailul tău" required aria-required="true">
            </div>
            <div class="form-group">
                <label for="telephone">Telefonul tău:</label>
                <input type="tel" name="telephone" id="telephone" class="form-control" placeholder="Telefonul tău" required aria-required="true">
            </div>
            <button type="submit" class="btn btn-primary">Înscriere</button>
        </form>
        
    </section>

    <section class="author-info">
        <h2>Despre Autor</h2>
        <p>Psih. <strong>Laura Elena Busuioc</strong> este un expert recunoscut în dezvoltarea copiilor si adolescenților, dedicată sprijinirii tinerilor și familiilor lor în navigarea complexităților adolescenței.Experienta si abilitatea de a construi relatii de incredere ii permit sa fie un partener valoros in parcursul de dezvoltare al tinerilor, contribuind la imbunatatirea starii lor de bine si la formarea unor abilitati de viata esentiale</p>
    </section>
    
    <div class="disclaimer">
        <p>
            <a href="javascript:void(0)" onclick="showPopup('disclaimerro', 'Disclaimer Română')">Disclaimer Română</a> |
            <a href="javascript:void(0)" onclick="showPopup('disclaimeren', 'Disclaimer English')">Disclaimer English</a> |
            <a href="javascript:void(0)" onclick="showPopup('gdprro', 'GDPR Română')">GDPR Română</a> |
            <a href="javascript:void(0)" onclick="showPopup('gdpren', 'GDPR English')">GDPR English</a>
        </p>
    </div>
</div>

</body>
</html>