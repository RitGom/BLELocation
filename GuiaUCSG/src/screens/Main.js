import React, { useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    StatusBar,
    SafeAreaView,
} from 'react-native';
import Tts from 'react-native-tts';

const Main = () => {
    useEffect(() => {
        // Configurar TTS al cargar el componente
        const initializeTts = async () => {
            try {
                // Verificar si TTS está disponible
                const engines = await Tts.engines();
                console.log('TTS Engines disponibles:', engines);

                if (engines.length === 0) {
                    console.warn('No hay motores TTS disponibles');
                    return;
                }

                // Configurar idioma con fallback
                try {
                    await Tts.setDefaultLanguage('es-ES');
                } catch (langError) {
                    console.warn('Idioma es-ES no disponible, usando idioma por defecto');
                    await Tts.setDefaultLanguage('en-US');
                }

                // Configurar velocidad y tono
                await Tts.setDefaultRate(0.5);
                await Tts.setDefaultPitch(1.0);

                // Listener para cuando TTS esté listo
                const onTtsInitialized = () => {
                    console.log('TTS inicializado correctamente');
                    // Reproducir mensaje después de que TTS esté completamente listo
                    setTimeout(() => {
                        Tts.speak('Bienvenido Usuario');
                    }, 1000);
                };

                // Listener para errores
                const onTtsError = (error) => {
                    console.error('Error en TTS:', error);
                };

                // Agregar listeners
                Tts.addEventListener('tts-start', onTtsInitialized);
                Tts.addEventListener('tts-error', onTtsError);

                // Intentar hablar para inicializar
                Tts.speak('');

            } catch (error) {
                console.error('Error inicializando TTS:', error);
                // Fallback: mostrar mensaje visual si TTS no funciona
                console.log('TTS no disponible, continuando sin voz');
            }
        };

        initializeTts();

        // Cleanup al desmontar el componente
        return () => {
            try {
                Tts.stop();
                Tts.removeAllListeners('tts-start');
                Tts.removeAllListeners('tts-error');
            } catch (error) {
                console.log('Error en cleanup TTS:', error);
            }
        };
    }, []);

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar backgroundColor="#8B0000" barStyle="light-content" />

            <View style={styles.header}>
                <Text style={styles.headerTitle}>Asistente de Voz</Text>
            </View>

            <View style={styles.mainContent}>
                <View style={styles.welcomeCard}>
                    <Text style={styles.welcomeText}>Bienvenido Usuario</Text>
                    <Text style={styles.subtitleText}>
                        Tu asistente de voz está listo
                    </Text>
                </View>

                <View style={styles.statusContainer}>
                    <View style={styles.statusIndicator} />
                    <Text style={styles.statusText}>Sistema Activo</Text>
                </View>
            </View>

            <View style={styles.footer}>
                <Text style={styles.footerText}>
                    Listo para recibir comandos de voz
                </Text>
            </View>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#2C2C2C', // Gris oscuro de fondo
    },
    header: {
        backgroundColor: '#8B0000', // Rojo oscuro
        paddingVertical: 20,
        paddingHorizontal: 20,
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: {
            width: 0,
            height: 2,
        },
        shadowOpacity: 0.25,
        shadowRadius: 3.84,
        elevation: 5,
    },
    headerTitle: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#FFFFFF',
    },
    mainContent: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: 30,
    },
    welcomeCard: {
        backgroundColor: '#404040', // Gris medio
        padding: 30,
        borderRadius: 15,
        alignItems: 'center',
        marginBottom: 40,
        shadowColor: '#000',
        shadowOffset: {
            width: 0,
            height: 4,
        },
        shadowOpacity: 0.3,
        shadowRadius: 4.65,
        elevation: 8,
        borderLeftWidth: 4,
        borderLeftColor: '#DC143C', // Rojo medio
    },
    welcomeText: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#FFFFFF',
        textAlign: 'center',
        marginBottom: 10,
    },
    subtitleText: {
        fontSize: 16,
        color: '#CCCCCC',
        textAlign: 'center',
    },
    statusContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#505050', // Gris claro
        paddingHorizontal: 20,
        paddingVertical: 15,
        borderRadius: 25,
    },
    statusIndicator: {
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: '#FF4500', // Rojo brillante
        marginRight: 10,
    },
    statusText: {
        fontSize: 16,
        color: '#FFFFFF',
        fontWeight: '500',
    },
    footer: {
        backgroundColor: '#1A1A1A', // Gris muy oscuro
        paddingVertical: 15,
        paddingHorizontal: 20,
        alignItems: 'center',
    },
    footerText: {
        fontSize: 14,
        color: '#AAAAAA',
        textAlign: 'center',
    },
});

export default Main;