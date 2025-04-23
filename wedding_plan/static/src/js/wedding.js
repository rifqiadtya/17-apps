$(document).ready(function ($) {
    if (document.getElementById('invitation-cover')) 
    {
        $(document).on('click', '#send_wish_button', function (event) {
            var vals = {
                'name': parseInt($("#partner_id").val()),
                'attend': $("#attend").val(),
                'wish': $("#wish").val(),
                'quantity': parseInt($("#quantity").val()),
            };
            console.log(vals)
            $.ajax({
                type: "POST",
                url: $("#base_url").val() + '/send-wish',
                contentType: "application/json",
                data: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": vals
                }),
                dataType: "json",
                success: function (response) {
                    console.log(response)
                    Swal.fire(
                        'Sent!',
                        'Thank you for your confirmation and wishes.',
                        'success'
                    )
                }
            });

        });


        $(document).on('click', '#copy_to_clipboard', function (event) {
            var copyText = document.getElementById("bca_rekening");
            
            // Copy the text inside the text field
            navigator.clipboard.writeText(copyText.innerHTML);
            
            // Alert the copied text
            alert("Copied the clipboard: " + copyText.innerHTML);

        });

        document.getElementById("invitation-button").onclick = function () {
            const invitationCover = document.querySelector(".invitation-cover");
            invitationCover.classList.toggle('hide');
            // for (let i = 0; i < document.querySelectorAll('.wedding-image-animated').length; i++) {
            //     sleep(2000).then(() => {
            //         console.log("After 2 seconds");
            //         showImage(i)
            //     });
            // }
        };

        function hideLoadingContent() {
            const loadingContainer = document.querySelector(".loading-container");
            loadingContainer.classList.toggle('hide-with-fade');
        }

        function setCountdown() {
            const second = 1000,
                minute = second * 60,
                hour = minute * 60,
                day = hour * 24;

            let today = new Date(),
                dd = String(today.getDate()).padStart(2, "0"),
                mm = String(today.getMonth() + 1).padStart(2, "0"),
                yyyy = today.getFullYear(),
                nextYear = yyyy + 1,
                dayMonth = "05/04/",
                birthday = dayMonth + yyyy;

            today = mm + "/" + dd + "/" + yyyy;
            if (today > birthday) {
                birthday = dayMonth + nextYear;
            }

            const countDown = new Date(birthday).getTime(),
                x = setInterval(function () {

                    const now = new Date().getTime(),
                        distance = countDown - now;

                    document.getElementById("days").innerText = Math.floor(distance / (day)),
                        document.getElementById("hours").innerText = Math.floor((distance % (day)) / (hour)),
                        document.getElementById("minutes").innerText = Math.floor((distance % (hour)) / (minute)),
                        document.getElementById("seconds").innerText = Math.floor((distance % (minute)) / second);

                    //do something later when date is reached
                    if (distance < 0) {
                        document.getElementById("headline").innerText = "It's my birthday!";
                        document.getElementById("countdown").style.display = "none";
                        document.getElementById("content").style.display = "block";
                        clearInterval(x);
                    }
                    //seconds
                }, 0)
        }
        setCountdown()
        setTimeout(hideLoadingContent, 2500);
    }

});