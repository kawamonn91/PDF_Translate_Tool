import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

val releaseSigning: Properties? = rootProject.file("keystore.properties")
    .takeIf { it.exists() }
    ?.let { file -> Properties().apply { file.inputStream().use(::load) } }

val mupdfRoot = rootProject.file("third_party/mupdf-1.28.5-source")

/** MuPDF の Java ラッパーを、ビルド時にコピーする(MuPDF のソースは Git に入れない) */
val syncMupdfJava = tasks.register<Copy>("syncMupdfJava") {
    from(mupdfRoot.resolve("platform/java/src/com/artifex/mupdf/fitz"))
    into(layout.projectDirectory.dir("src/main/java/com/artifex/mupdf/fitz"))
}

/** ndk-build で作った libmupdf_java.so を、ABI ごとにコピーする */
val syncMupdfNative = tasks.register<Copy>("syncMupdfNative") {
    from(mupdfRoot.resolve("libs"))
    include("**/libmupdf_java.so")
    into(layout.projectDirectory.dir("src/main/jniLibs"))
}

android {
    namespace = "com.kawamonn.pdfjatranslator"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.kawamonn.pdfjatranslator"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        if (releaseSigning != null) {
            create("release") {
                storeFile = rootProject.file(releaseSigning.getProperty("storeFile"))
                storePassword = releaseSigning.getProperty("storePassword")
                keyAlias = releaseSigning.getProperty("keyAlias")
                keyPassword = releaseSigning.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (releaseSigning != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

tasks.named("preBuild") {
    dependsOn(syncMupdfJava, syncMupdfNative)
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)

    testImplementation(libs.junit)
}
