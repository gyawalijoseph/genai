package com.axp.microdose.examples;

import com.axp.logging.schema.v0_1.Structured;
import com.axp.microdose.commons.MicrodoseConstants;
import com.axp.microdose.data.MicrodoseFunction;
import io.vertx.core.Future;
import io.vertx.core.MultiMap;
import io.vertx.core.eventbus.DeliveryOptions;
import io.vertx.core.eventbus.Message;
import io.vertx.core.json.JsonObject;
import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.http.HttpStatus;


public class ReadHelloWorldVerticle extends microdoseFunction<JsonObject> {

    private static final String NAME = "name";

    @Override
    protected Future<Void> initFunction(Structured classMarker){
        // The below line is only needed if plan to mask PII data
        // logger = LoggerFactory.getLogger(this.getClass(), LogMaskingType.ASTERIK);
        // return the future
        return Future.succeededFuture();
    }

    @Override
    protected void handle(Message<JsonObject> message, Structured messageMarker){
        try {
            var requestBody = message.body();

            logger.info(messageMarker, "Received request: {}", requestBody);
            if (!isRequestValid(message, messageMarker)) {
                return;
            }

            MultiMap headers = MultiMap.caseInsensitiveMultiMap();
            headers.set(MicrodoseConstants.HTTP_STATUS_CODE, String.valueOf(HttpStatus.SC_OK));
            DeliveryOptions replyOptions = new DeliveryOptions().setHeaders(headers);
            message.reply(String.format("Hello BG, from %s!!!\n", requestBody.getString(NAME)), replyOptions);
        } catch (Exception e){
            logger.error(messageMarker, "Request failed with an exception: {}", ExceptionUtils.getStackTrace(e));   
            message.fail(HttpStatus.SC_INTERNAL_SERVER_ERROR, "Internal server error: " + ExceptionUtils.getStackTrace(e));
        }
    }

    private boolean isRequestValid(Message<JsonObject> message, Structured messageMarker){
        if (message.body() == null) {
            logger.warn(messageMarker, "Body should be a valid JsonObject")
            message.fail(400, "Body should be a valid JsonObject");
            return False;
        }

        if (message.body().isEmpty() || message.body().getString(NAME, StringUtils.EMPTY).isBlank()) {
            logger.warn(messageMarker, "Missing or empty 'name' field in the request body")
            message.fail(400, "Missing or empty 'name' field in the request body");
            return False;
        }
        return True;
    }
}