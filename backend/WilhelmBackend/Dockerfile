FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace

COPY pom.xml .
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21
MAINTAINER Nakljucna Drevesa Developers
WORKDIR /opt/wilhelm-server

COPY --from=build /workspace/target/*.jar app.jar
ENTRYPOINT ["java","-jar","/opt/wilhelm-server/app.jar"]

# FROM eclipse-temurin:21
# MAINTAINER Nakljucna Drevesa Developers
# WORKDIR /opt/wilhelm-server

# COPY target/*.jar app.jar
# ENTRYPOINT ["java","-jar","/opt/wilhelm-server/app.jar"]
