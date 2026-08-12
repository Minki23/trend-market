# Stage 1 - Build the application
FROM eclipse-temurin:21 AS builder

WORKDIR /app

# Copy Gradle files first (improves layer caching)
COPY gradlew .
COPY gradle gradle
COPY build.gradle .
COPY settings.gradle .

# Copy source code
COPY src src

# Make wrapper executable and build the project
RUN chmod +x gradlew
RUN ./gradlew build -x test

# Stage 2 - Create runtime image
FROM eclipse-temurin:21

WORKDIR /app

COPY --from=builder /app/build/libs/*.jar app.jar

ENTRYPOINT ["java", "-jar", "app.jar"]