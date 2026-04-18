FROM eclipse-temurin:21
MAINTAINER Nakljucna Drevesa Developers
WORKDIR /opt/wilhelm-server

COPY target/*.jar app.jar
ENTRYPOINT ["java","-jar","/opt/wilhelm-server/app.jar"]
