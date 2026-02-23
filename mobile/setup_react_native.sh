#!/bin/bash
# Script to set up React Native project for the Health Navigation mobile app

set -e  # Exit on any error

# Create directory structure
mkdir -p app/src/{api,components,screens,hooks,navigation,utils,types,assets,contexts}

# Create essential files

# Package.json template
cat > app/package.json << EOF
{
  "name": "health-navigation-mobile",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "android": "react-native run-android",
    "ios": "react-native run-ios",
    "start": "react-native start",
    "test": "jest",
    "lint": "eslint .",
    "prepare-dev": "npm run build:types",
    "build:types": "cd ../web && tsc --declaration --emitDeclarationOnly --outDir ../mobile/app/src/types/web-types"
  },
  "dependencies": {
    "@react-navigation/bottom-tabs": "^6.5.8",
    "@react-navigation/native": "^6.1.7",
    "@react-navigation/native-stack": "^6.9.13",
    "axios": "^1.4.0",
    "react": "18.2.0",
    "react-native": "0.72.3",
    "react-native-safe-area-context": "^4.7.1",
    "react-native-screens": "^3.22.1",
    "react-native-svg": "^13.9.0"
  },
  "devDependencies": {
    "@babel/core": "^7.20.0",
    "@babel/preset-env": "^7.20.0",
    "@babel/runtime": "^7.20.0",
    "@react-native/eslint-config": "^0.72.2",
    "@react-native/metro-config": "^0.72.9",
    "@tsconfig/react-native": "^3.0.0",
    "@types/react": "^18.0.24",
    "babel-jest": "^29.2.1",
    "eslint": "^8.19.0",
    "jest": "^29.2.1",
    "metro-react-native-babel-preset": "0.76.7",
    "prettier": "^2.4.1",
    "typescript": "4.8.4"
  }
}
EOF

# TypeScript configuration
cat > app/tsconfig.json << EOF
{
  "extends": "@tsconfig/react-native/tsconfig.json",
  "compilerOptions": {
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "*": ["src/*"],
      "tests": ["tests/*"],
      "@components/*": ["src/components/*"],
      "@screens/*": ["src/screens/*"],
      "@utils/*": ["src/utils/*"],
      "@api/*": ["src/api/*"],
      "@types/*": ["src/types/*"],
      "@assets/*": ["src/assets/*"],
      "@hooks/*": ["src/hooks/*"],
      "@contexts/*": ["src/contexts/*"]
    }
  }
}
EOF

# Environment configuration
cat > app/src/utils/config.ts << EOF
/**
 * Environment configuration for the Health Navigation mobile app
 */

type Environment = 'development' | 'staging' | 'production';

interface Config {
  API_URL: string;
  API_TIMEOUT: number;
  USE_MOCK_DATA: boolean;
  ENABLE_LOGGER: boolean;
}

const ENV: Environment = (process.env.REACT_APP_ENV as Environment) || 'development';

const configs: Record<Environment, Config> = {
  development: {
    API_URL: 'http://localhost:8000',
    API_TIMEOUT: 30000,
    USE_MOCK_DATA: false,
    ENABLE_LOGGER: true,
  },
  staging: {
    API_URL: 'https://api-staging.healthnavigation.com',
    API_TIMEOUT: 30000,
    USE_MOCK_DATA: false,
    ENABLE_LOGGER: true,
  },
  production: {
    API_URL: 'https://api.healthnavigation.com',
    API_TIMEOUT: 30000,
    USE_MOCK_DATA: false,
    ENABLE_LOGGER: false,
  },
};

export default configs[ENV];
EOF

# API client
cat > app/src/api/client.ts << EOF
/**
 * API client for the Health Navigation mobile app
 * Uses the same API contract as the web client
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import config from '../utils/config';
import { UserContext } from '../types/userContext';

class ApiClient {
  private client: AxiosInstance;
  private static instance: ApiClient;

  private constructor() {
    this.client = axios.create({
      baseURL: config.API_URL,
      timeout: config.API_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  public static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient();
    }
    return ApiClient.instance;
  }

  // API endpoints using the same contract as the web client

  async getFoodRecommendations(context: UserContext) {
    return this.post('/api/recommendations/foods', context);
  }

  async getHealthMapPosition(context: UserContext) {
    return this.post('/api/health-map/position', context);
  }

  async getSafestPath(context: UserContext) {
    return this.post('/api/health-map/safest-path', context);
  }

  async getEarlySignals(context: UserContext) {
    return this.post('/api/guidance/early-signals', context);
  }

  async getGeneralGuidance(context: UserContext) {
    return this.post('/api/guidance/general', context);
  }

  async getFoodChain(food: string) {
    return this.get(\`/api/kg/food-chain?food=\${encodeURIComponent(food)}\`);
  }

  // Base methods
  private async get(url: string, config?: AxiosRequestConfig) {
    try {
      const response = await this.client.get(url, config);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  private async post(url: string, data: any, config?: AxiosRequestConfig) {
    try {
      const response = await this.client.post(url, data, config);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  private handleError(error: any) {
    // Error handling logic
    if (config.ENABLE_LOGGER) {
      console.error('API Error:', error);
    }
  }
}

export default ApiClient.getInstance();
EOF

# User context type
cat > app/src/types/userContext.ts << EOF
/**
 * User context model
 * Matches the model from the web client
 */

export interface UserContext {
  age?: number;
  gender?: 'male' | 'female' | 'other';
  ethnicity?: string;
  conditions?: string[];
  symptoms?: string[];
  medications?: string[];
  goals?: string[];
  location?: string;
  way_of_living?: string;
  culture?: string;
}
EOF

# App entry point
cat > app/App.tsx << EOF
/**
 * Health Navigation Mobile App
 */

import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'react-native';

// Placeholder for future navigation setup
const App = () => {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar barStyle="dark-content" />
        {/* Main Navigator will go here */}
      </NavigationContainer>
    </SafeAreaProvider>
  );
};

export default App;
EOF

# README update
cat > app/README.md << EOF
# Health Navigation Mobile App

React Native mobile application for the Health Navigation platform.

## Setup

1. Install dependencies:
   \`\`\`
   npm install
   \`\`\`

2. For iOS, install CocoaPods dependencies:
   \`\`\`
   cd ios && pod install
   \`\`\`

3. Start the app:
   \`\`\`
   # iOS
   npm run ios

   # Android
   npm run android
   \`\`\`

## Architecture

The app follows the same principles as the web client:
- Zero-error tolerance (evidence-based)
- Term standardization
- Trust visualization (blue/green/gold badges)

### Directory Structure

- \`/api\`: API client and services
- \`/components\`: Reusable UI components
- \`/screens\`: App screens
- \`/navigation\`: Navigation configuration
- \`/hooks\`: Custom React hooks
- \`/utils\`: Utility functions
- \`/types\`: TypeScript type definitions
- \`/assets\`: Images, fonts, etc.
- \`/contexts\`: React Context providers

### API Integration

Uses the same API contract as the web client, with \`UserContext\` as the primary input model:
- \`/api/recommendations/foods\`
- \`/api/health-map/position\`
- \`/api/health-map/safest-path\`
- \`/api/guidance/early-signals\`
- \`/api/guidance/general\`
- \`/api/kg/food-chain\`
EOF

echo "Initial React Native project structure set up successfully!"
echo "To complete the setup:"
echo "1. Run 'npx react-native init HealthNavigation' in the mobile directory"
echo "2. Copy these template files into the created project"
echo "3. Run 'npm install' to install dependencies"