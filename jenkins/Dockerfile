# Tracks the current Jenkins LTS line. Plugin versions float with that
# image's update center so the demo stays installable without a pin that
# drifts out of compatibility.
FROM jenkins/jenkins:lts-jdk17

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
